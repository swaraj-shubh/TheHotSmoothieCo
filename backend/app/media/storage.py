"""Media storage behind a small interface so Cloudinary can be swapped for S3/R2/GCS by adding one
class and changing MEDIA_PROVIDER — product code only ever sees `StoredMedia`."""

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import AppError

log = structlog.get_logger()

MAX_IMAGE_BYTES = 15 * 1024 * 1024
# Magic-byte sniffing: the client-supplied Content-Type and filename are never trusted.
_SIGNATURES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}


class InvalidUpload(AppError):
    code, message = "INVALID_UPLOAD", "Upload must be a JPEG, PNG or WebP image under 15 MB"


class MediaStorageUnavailable(AppError):
    status_code, code, message = 503, "MEDIA_STORAGE_UNAVAILABLE", "Image storage is temporarily unavailable"


def sniff_image(data: bytes) -> str:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InvalidUpload()
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    for sig, fmt in _SIGNATURES.items():
        if data.startswith(sig):
            return fmt
    raise InvalidUpload()


@dataclass(frozen=True)
class StoredMedia:
    provider: str
    key: str
    url: str
    thumbnail_url: str
    width: int | None
    height: int | None
    format: str | None
    bytes: int


class MediaStorage(Protocol):
    provider: str

    async def upload(self, data: bytes, folder: str) -> StoredMedia: ...
    async def delete(self, key: str) -> None: ...
    def url_for(self, key: str, *, width: int, height: int | None = None) -> str: ...


class CloudinaryStorage:
    """Uses Cloudinary's signed REST upload API directly (the official SDK is synchronous)."""

    provider = "cloudinary"

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        self.cloud_name, self.api_key, self.api_secret = cloud_name, api_key, api_secret
        self.base = f"https://api.cloudinary.com/v1_1/{cloud_name}/image"

    def _sign(self, params: dict[str, str]) -> dict[str, str]:
        to_sign = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hashlib.sha1((to_sign + self.api_secret).encode()).hexdigest()  # noqa: S324 (Cloudinary's scheme)
        return {**params, "api_key": self.api_key, "signature": signature}

    def url_for(self, key: str, *, width: int, height: int | None = None) -> str:
        crop = f"c_fill,w_{width},h_{height}" if height else f"c_limit,w_{width}"
        return f"https://res.cloudinary.com/{self.cloud_name}/image/upload/{crop},q_auto,f_auto/{key}"

    async def upload(self, data: bytes, folder: str) -> StoredMedia:
        params = self._sign({"folder": folder, "timestamp": str(int(time.time()))})
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{self.base}/upload", data=params, files={"file": data})
                r.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("media_upload_failed", provider=self.provider, error=str(exc))
            raise MediaStorageUnavailable() from exc
        body = r.json()
        return StoredMedia(
            provider=self.provider,
            key=body["public_id"],
            url=body["secure_url"],
            thumbnail_url=self.url_for(body["public_id"], width=400, height=400),
            width=body.get("width"),
            height=body.get("height"),
            format=body.get("format"),
            bytes=body.get("bytes", len(data)),
        )

    async def delete(self, key: str) -> None:
        params = self._sign({"public_id": key, "timestamp": str(int(time.time()))})
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                (await client.post(f"{self.base}/destroy", data=params)).raise_for_status()
        except httpx.HTTPError as exc:
            # Orphaned files cost storage, not correctness; log for cleanup rather than failing the request.
            log.error("media_delete_failed", provider=self.provider, key=key, error=str(exc))


def get_media_storage() -> MediaStorage:
    s = get_settings()
    if not (s.cloudinary_cloud_name and s.cloudinary_api_key and s.cloudinary_api_secret):
        raise MediaStorageUnavailable("Image storage is not configured")
    return CloudinaryStorage(
        s.cloudinary_cloud_name, s.cloudinary_api_key, s.cloudinary_api_secret.get_secret_value()
    )
