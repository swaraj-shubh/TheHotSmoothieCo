"""Audit trail for admin mutations, recorded centrally so no endpoint can forget it.

The actor is put on request.state by require_roles; after the response has been sent we write
one row with what was attempted, by whom, and the outcome (status code). Writing happens after
the response, in its own session, so auditing never slows down or breaks the admin action.
ponytail: a crash between the business commit and the audit insert loses that one row; move to
in-transaction auditing if compliance ever requires a guaranteed trail.
"""

import json
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.audit.models import AuditLog
from app.core.clientip import client_ip
from app.core.database import SessionLocal

log = structlog.get_logger()

API_PREFIX = "/api/v1"
AUDITED_PREFIX = f"{API_PREFIX}/admin"
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY = 64 * 1024
SECRET_HINTS = ("password", "token", "secret", "signature", "otp", "card")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if any(h in k.lower() for h in SECRET_HINTS) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value[:100]]
    return value


def _body_summary(body: bytes, content_type: str) -> dict | None:
    if not body:
        return None
    if "application/json" in content_type:
        try:
            return {"json": redact(json.loads(body))}
        except ValueError:
            pass
    # Uploads (images, CSV): record the shape, not the content.
    return {"content_type": content_type[:100], "bytes": len(body)}


def _target(path_params: dict, route_path: str) -> tuple[str | None, str | None]:
    target_id = next((str(v) for v in path_params.values() if _is_uuid(v)), None)
    parts = [p for p in route_path.removeprefix(AUDITED_PREFIX).split("/") if p and not p.startswith("{")]
    return (parts[0] if parts else None), target_id


def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class AuditMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in MUTATING
            or not scope["path"].startswith(AUDITED_PREFIX)
        ):
            await self.app(scope, receive, send)
            return

        captured = bytearray()
        status = 500

        async def receive_wrapper() -> Message:
            message = await receive()
            if message["type"] == "http.request" and len(captured) < MAX_BODY:
                captured.extend(message.get("body", b"")[: MAX_BODY - len(captured)])
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            await self._record(scope, bytes(captured), status)

    async def _record(self, scope: Scope, body: bytes, status: int) -> None:
        try:
            headers = {k.decode().lower(): v.decode(errors="replace") for k, v in scope["headers"]}
            actor = (scope.get("state") or {}).get("actor") or {}
            route: str = getattr(scope.get("route"), "path", None) or scope["path"]
            if not route.startswith(API_PREFIX):  # routes of included routers are relative to the prefix
                route = API_PREFIX + route
            target_type, target_id = _target(scope.get("path_params") or {}, route)
            async with SessionLocal() as db:
                db.add(
                    AuditLog(
                        actor_user_id=uuid.UUID(actor["id"]) if actor.get("id") else None,
                        actor_email=actor.get("email"),
                        actor_roles=actor.get("roles"),
                        action=f"{scope['method']} {route}"[:200],
                        method=scope["method"],
                        path=scope["path"][:500],
                        status_code=status,
                        target_type=target_type,
                        target_id=target_id,
                        request_id=structlog.contextvars.get_contextvars().get("request_id"),
                        ip_address=client_ip(scope),
                        user_agent=(headers.get("user-agent") or "")[:512] or None,
                        request_body=_body_summary(body, headers.get("content-type", "")),
                    )
                )
                await db.commit()
        except Exception as exc:  # auditing must never break the request
            log.exception("audit_write_failed", path=scope.get("path"), exc_info=exc)
