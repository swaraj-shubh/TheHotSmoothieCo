"""Request body size limits, enforced before any parsing.

Without this, Starlette's multipart parser spools an arbitrarily large upload to disk (and JSON
bodies into memory) before the endpoint's own checks ever run.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_LIMIT = 1 * 1024 * 1024  # JSON APIs
UPLOAD_LIMIT = 16 * 1024 * 1024  # image uploads (15 MB cap + multipart overhead), CSV import
UPLOAD_SUFFIXES = ("/media", "/import")


class BodyTooLarge(Exception):
    pass


def _limit_for(path: str) -> int:
    return UPLOAD_LIMIT if path.rstrip("/").endswith(UPLOAD_SUFFIXES) else DEFAULT_LIMIT


async def _reject(send: Send, limit: int) -> None:
    body = json.dumps(
        {
            "success": False,
            "error": {"code": "PAYLOAD_TOO_LARGE", "message": f"Request body exceeds {limit // 1024} KB"},
        }
    ).encode()
    await send(
        {"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]}
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = _limit_for(scope["path"])
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            await _reject(send, limit)  # refused before reading a single byte
            return

        received = 0
        exceeded = False
        replaced = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:  # chunked bodies (no Content-Length) that lie about their size
                    exceeded = True
                    raise BodyTooLarge()
            return message

        async def guarded_send(message: Message) -> None:
            # Frameworks may catch BodyTooLarge while parsing and answer 400; substitute the real 413.
            nonlocal replaced
            if exceeded:
                if message["type"] == "http.response.start" and not replaced:
                    replaced = True
                    await _reject(send, limit)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except BodyTooLarge:
            if not replaced:
                await _reject(send, limit)
