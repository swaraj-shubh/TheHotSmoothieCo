import base64
import json
from typing import Any

from pydantic import BaseModel

from app.core.exceptions import AppError

MAX_LIMIT = 100


class InvalidCursor(AppError):
    code, message = "INVALID_CURSOR", "Invalid pagination cursor"


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(*values: Any) -> str:
    """Opaque keyset cursor: the sort key + id of the last row on the page."""
    return base64.urlsafe_b64encode(json.dumps(values, default=str).encode()).decode()


def decode_cursor(cursor: str, size: int) -> list:
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except ValueError as exc:
        raise InvalidCursor() from exc
    if not isinstance(values, list) or len(values) != size:
        raise InvalidCursor()
    return values
