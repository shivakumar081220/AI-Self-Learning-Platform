import base64
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from ..config import settings

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_COUNT = 3
MAX_TOTAL_IMAGE_BYTES = 10 * 1024 * 1024

_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


@dataclass(frozen=True)
class ValidatedImage:
    storage_key: str
    content_type: str
    size_bytes: int
    data: bytes


def _is_valid_signature(content_type: str, data: bytes) -> bool:
    signatures = _SIGNATURES[content_type]
    if content_type == "image/webp":
        return len(data) >= 12 and data.startswith(signatures[0]) and data[8:12] == b"WEBP"
    return any(data.startswith(signature) for signature in signatures)


def validate_uploads(files: list[UploadFile]) -> list[ValidatedImage]:
    if not files:
        raise ValueError("Attach at least one supported image.")
    if len(files) > MAX_IMAGE_COUNT:
        raise ValueError(f"Attach no more than {MAX_IMAGE_COUNT} images at a time.")
    validated: list[ValidatedImage] = []
    total_size = 0
    for upload in files:
        content_type = (upload.content_type or "").lower()
        if content_type not in _SIGNATURES:
            raise ValueError("Use a JPEG, PNG, GIF, or WebP image.")
        data = upload.file.read(MAX_IMAGE_BYTES + 1)
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Each image must be no larger than 5 MB.")
        if not _is_valid_signature(content_type, data):
            raise ValueError("An image's contents do not match its declared file type.")
        total_size += len(data)
        if total_size > MAX_TOTAL_IMAGE_BYTES:
            raise ValueError("The combined image upload must be no larger than 10 MB.")
        validated.append(
            ValidatedImage(
                storage_key=f"{uuid.uuid4().hex}{mimetypes.guess_extension(content_type) or '.img'}",
                content_type=content_type,
                size_bytes=len(data),
                data=data,
            )
        )
    return validated


def save_private_image(image: ValidatedImage) -> Path:
    root = Path(settings.tutor_upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / image.storage_key).resolve()
    if target.parent != root:
        raise ValueError("Invalid image storage key")
    target.write_bytes(image.data)
    return target


def remove_private_images(images: list[ValidatedImage]) -> None:
    root = Path(settings.tutor_upload_dir).resolve()
    for image in images:
        target = (root / image.storage_key).resolve()
        if target.parent == root:
            target.unlink(missing_ok=True)


def image_data_url(image: ValidatedImage) -> str:
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.content_type};base64,{encoded}"