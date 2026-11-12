import time
import uuid
from io import BytesIO

import cloudinary
import cloudinary.api
import cloudinary.uploader
from cloudinary.utils import api_sign_request, cloudinary_url, private_download_url
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


def create_tutor_video_upload_signature(
    tutor_user_id: str,
) -> dict[str, str | int]:
    """
    Generate a signed direct-upload authorization for one temporary
    introduction-video asset.

    The API secret is used only on the backend and is never returned.
    """
    configure_cloudinary()

    cloud_config = cloudinary.config()

    if (
        not cloud_config.cloud_name
        or not cloud_config.api_key
        or not cloud_config.api_secret
    ):
        raise RuntimeError("Cloudinary is not properly configured.")

    timestamp = int(time.time())

    public_id = f"tutova/tutor-introductions/{tutor_user_id}/pending-{uuid.uuid4().hex}"

    params_to_sign = {
        "timestamp": timestamp,
        "public_id": public_id,
    }

    signature = api_sign_request(
        params_to_sign,
        cloud_config.api_secret,
    )

    return {
        "cloud_name": cloud_config.cloud_name,
        "api_key": cloud_config.api_key,
        "timestamp": timestamp,
        "signature": signature,
        "public_id": public_id,
    }


def get_tutor_video_resource(public_id: str) -> dict:
    """Retrieve a Cloudinary video asset for server-side validation."""
    configure_cloudinary()

    return cloudinary.api.resource(
        public_id,
        resource_type="video",
    )


def finalize_tutor_video_upload(
    temporary_public_id: str,
    tutor_user_id: str,
) -> str:
    """
    Validate the uploaded temporary video and rename it to the
    tutor's permanent introduction-video public ID.
    """
    configure_cloudinary()

    expected_prefix = f"tutova/tutor-introductions/{tutor_user_id}/pending-"

    if not temporary_public_id.startswith(expected_prefix):
        raise ValueError("Invalid introduction video public ID.")

    temporary_suffix = temporary_public_id.removeprefix(expected_prefix)

    if not temporary_suffix or "/" in temporary_suffix:
        raise ValueError("Invalid temporary introduction video ID.")

    asset = get_tutor_video_resource(temporary_public_id)

    if asset.get("resource_type") != "video":
        raise ValueError("The uploaded asset is not a video.")

    if asset.get("format", "").lower() not in {"mp4", "webm"}:
        raise ValueError("Only MP4 and WebM videos are supported.")

    file_size = int(asset.get("bytes") or 0)

    if file_size <= 0 or file_size > MAX_INTRO_VIDEO_SIZE:
        raise ValueError("Introduction video must not exceed 100 MB.")

    duration = float(asset.get("duration") or 0)

    if duration <= 0 or duration > MAX_INTRO_VIDEO_DURATION:
        raise ValueError("Introduction video must not exceed 120 seconds.")

    permanent_public_id = tutor_video_public_id(tutor_user_id)

    cloudinary.uploader.rename(
        temporary_public_id,
        permanent_public_id,
        resource_type="video",
        overwrite=True,
        invalidate=True,
    )

    return permanent_public_id


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
