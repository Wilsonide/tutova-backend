import uuid
from io import BytesIO

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url, private_download_url
from fastapi import HTTPException, status

from app.core.config import settings

MAX_INTRO_VIDEO_SIZE = 100 * 1024 * 1024
MAX_INTRO_VIDEO_DURATION = 120

ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
}

ALLOWED_PROFILE_PICTURE_TYPES = {
    "image/jpeg": ("jpg", "jpeg"),
    "image/png": ("png",),
    "image/webp": ("webp",),
}

ALLOWED_IDENTITY_DOCUMENT_TYPES = {
    "application/pdf": ("pdf",),
    "image/jpeg": ("jpg", "jpeg"),
    "image/png": ("png",),
}


def configure_cloudinary() -> None:
    cloud_name = settings.CLOUDINARY_CLOUD_NAME.strip()
    api_key = settings.CLOUDINARY_API_KEY.strip()
    api_secret = settings.CLOUDINARY_API_SECRET.strip()

    if not all((cloud_name, api_key, api_secret)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary hosting is not configured.",
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def _validate_file_signature(content: bytes, content_type: str) -> bool:
    """Check the file's actual signature rather than trusting its MIME type."""

    if content_type == "application/pdf":
        return content.startswith(b"%PDF-")

    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")

    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")

    if content_type == "image/webp":
        return (
            len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        )

    return False


# ---------------------------------------------------------------------
# Tutor profile pictures: public image assets
# ---------------------------------------------------------------------


def upload_tutor_profile_picture(
    content: bytes,
    tutor_user_id: str,
    content_type: str,
) -> dict:
    configure_cloudinary()

    allowed_extensions = ALLOWED_PROFILE_PICTURE_TYPES.get(content_type)
    if not allowed_extensions or not _validate_file_signature(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Profile pictures must be valid JPEG, PNG, or WebP images.",
        )

    extension = allowed_extensions[0]
    public_id = f"tutova/tutor-profile-pictures/{tutor_user_id}/{uuid.uuid4().hex}"

    try:
        return cloudinary.uploader.upload(
            BytesIO(content),
            resource_type="image",
            public_id=public_id,
            overwrite=False,
            invalidate=True,
            format=extension,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not upload the profile picture.",
        ) from exc


def get_tutor_profile_picture_url(public_id: str | None) -> str | None:
    if not public_id:
        return None

    try:
        configure_cloudinary()

        url, _ = cloudinary_url(
            public_id,
            resource_type="image",
            secure=True,
        )
        return url

    except Exception:
        return None


def delete_tutor_profile_picture(public_id: str) -> None:
    configure_cloudinary()

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
            invalidate=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete the profile picture from storage.",
        ) from exc


# ---------------------------------------------------------------------
# Tutor introduction videos: existing public video workflow
# ---------------------------------------------------------------------


def tutor_video_public_id(tutor_user_id: str) -> str:
    return f"tutova/tutor-introductions/{tutor_user_id}/introduction"


def upload_tutor_video(file, tutor_user_id: str) -> dict:
    configure_cloudinary()

    final_public_id = tutor_video_public_id(tutor_user_id)
    temporary_public_id = (
        f"tutova/tutor-introductions/{tutor_user_id}/pending-{uuid.uuid4().hex}"
    )

    try:
        uploaded = cloudinary.uploader.upload(
            file,
            resource_type="video",
            public_id=temporary_public_id,
            overwrite=False,
            chunk_size=6_000_000,
            allowed_formats=["mp4", "webm"],
        )

        duration = uploaded.get("duration")
        if duration is not None and duration > MAX_INTRO_VIDEO_DURATION:
            cloudinary.uploader.destroy(
                temporary_public_id,
                resource_type="video",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Introduction videos must not exceed 2 minutes.",
            )

        return cloudinary.uploader.rename(
            temporary_public_id,
            final_public_id,
            resource_type="video",
            overwrite=True,
            invalidate=True,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not upload the introduction video.",
        ) from exc


def delete_tutor_video(public_id: str) -> None:
    configure_cloudinary()

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type="video",
            invalidate=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete the introduction video.",
        ) from exc


def get_tutor_video_url(public_id: str | None) -> str | None:
    if not public_id:
        return None

    try:
        configure_cloudinary()

        url, _ = cloudinary_url(
            public_id,
            resource_type="video",
            secure=True,
        )
        return url

    except Exception:
        return None


# ---------------------------------------------------------------------
# Identity documents: authenticated raw assets
# ---------------------------------------------------------------------


def upload_tutor_identity_document(
    content: bytes,
    tutor_user_id: str,
    content_type: str,
) -> dict:
    configure_cloudinary()

    allowed_extensions = ALLOWED_IDENTITY_DOCUMENT_TYPES.get(content_type)

    if not allowed_extensions or not _validate_file_signature(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Identity documents must be valid PDF, JPEG, or PNG files.",
        )

    extension = allowed_extensions[0]

    public_id = (
        f"tutova/identity-documents/{tutor_user_id}/{uuid.uuid4().hex}.{extension}"
    )

    try:
        uploaded = cloudinary.uploader.upload(
            BytesIO(content),
            resource_type="raw",
            type="authenticated",
            public_id=public_id,
            overwrite=False,
            use_filename=False,
            unique_filename=False,
        )

        if not isinstance(uploaded, dict):
            raise RuntimeError("Cloudinary returned an unexpected upload response.")

        returned_public_id = uploaded.get("public_id")

        if not returned_public_id:
            raise RuntimeError("Cloudinary did not return a public_id.")

        # Raw uploads may not include a separate format field.
        file_format = (uploaded.get("format") or extension).lower().lstrip(".")

        if file_format not in {"pdf", "jpg", "jpeg", "png"}:
            raise RuntimeError("Cloudinary returned an unsupported document format.")

        return {
            **uploaded,
            "public_id": returned_public_id,
            "format": file_format,
        }

    except HTTPException:
        raise
    except Exception as exc:
        # Log the actual exception server-side; never log document contents.
        import logging

        logging.getLogger(__name__).exception(
            "Cloudinary identity document upload failed."
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not securely upload the identity document.",
        ) from exc


def get_identity_document_download_url(
    public_id: str,
    file_format: str,
) -> str:
    configure_cloudinary()

    if not public_id or not file_format:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity document is unavailable.",
        )

    try:
        import time

        expires_at = (
            int(time.time()) + settings.CLOUDINARY_IDENTITY_DOCUMENT_URL_TTL_SECONDS
        )

        return private_download_url(
            public_id,
            file_format,
            resource_type="raw",
            type="authenticated",
            expires_at=expires_at,
            attachment=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate the secure document download link.",
        ) from exc


def delete_tutor_identity_document(public_id: str) -> None:
    configure_cloudinary()

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type="raw",
            type="authenticated",
            invalidate=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete the identity document from storage.",
        ) from exc
