"""The client's real IP, for rate limiting, sessions and the audit log.

X-Forwarded-For is client-controlled at its left end, so it's only trusted as far as our own
proxies appended it:
- CLIENT_IP_HEADER (e.g. `cf-connecting-ip` behind Cloudflare): set by the edge, can't be forged
  as long as the origin only accepts traffic from that edge.
- TRUSTED_PROXY_HOPS=N: take the entry the N-th proxy from us appended (rightmost = 1).
- otherwise the TCP peer.
Requests from our own Next.js server (BFF) carry the visitor's IP in X-Client-IP, trusted only
when accompanied by the shared X-BFF-Secret.
"""

import hmac
import ipaddress

from starlette.types import Scope

from app.core.config import get_settings


def _valid(ip: str) -> str | None:
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        return None


def _headers(scope: Scope) -> dict[str, str]:
    return {k.decode().lower(): v.decode(errors="replace") for k, v in scope.get("headers", [])}


def is_trusted_bff(scope: Scope) -> bool:
    """Request made by our own Next.js server (it proves it with the shared BFF secret)."""
    secret = get_settings().bff_secret
    sent = _headers(scope).get("x-bff-secret", "")
    if secret is None or not sent:
        return False
    return hmac.compare_digest(sent.encode(), secret.get_secret_value().encode())


def end_user_ip(scope: Scope) -> str | None:
    """The visitor's IP as forwarded by the trusted BFF, if any."""
    return _valid(_headers(scope).get("x-client-ip", "")) if is_trusted_bff(scope) else None


def client_ip(scope: Scope) -> str:
    s = get_settings()
    headers = _headers(scope)
    # Behind the BFF every request comes from the Next.js server; it forwards the visitor's IP.
    if forwarded := end_user_ip(scope):
        return forwarded
    if s.client_ip_header and (ip := _valid(headers.get(s.client_ip_header.lower(), ""))):
        return ip
    if s.trusted_proxy_hops and (xff := headers.get("x-forwarded-for")):
        parts = [p for p in xff.split(",") if p.strip()]
        if len(parts) >= s.trusted_proxy_hops and (ip := _valid(parts[-s.trusted_proxy_hops])):
            return ip
    peer = scope.get("client")
    return peer[0] if peer else "unknown"
