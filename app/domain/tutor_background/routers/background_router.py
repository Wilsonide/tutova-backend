from typing import Annotated
from fastapi import APIRouter, File, Query, UploadFile, HTTPException
from app.core.dependencies import DBSession, RequireTutor, RequireAnyAdmin
from app.domain.tutor_background.schemas.background import BackgroundReplace, InstitutionSuggestion
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.domain.tutor_background.services.background_service import BackgroundService

router = APIRouter(prefix="/tutors/profile", tags=["Tutor Background"])

@router.get("/background")
async def get_background(current_user: RequireTutor, db: DBSession):
    data = await BackgroundService(db).list(current_user)
    return {key: [_serialize(row) for row in rows] for key, rows in data.items()}

def _serialize(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}

@router.put("/background")
async def replace_background(data: BackgroundReplace, current_user: RequireTutor, db: DBSession):
    result = await BackgroundService(db).replace(current_user, data)
    await db.commit()
    return {key: [_serialize(row) for row in rows] for key, rows in result.items()}

@router.get("/institutions")
async def search_institutions(current_user: RequireTutor, db: DBSession, q: Annotated[str, Query(min_length=2, max_length=255)], country_code: Annotated[str | None, Query(min_length=2, max_length=2)] = None):
    rows = await BackgroundService(db).search_institutions(q, country_code)
    return [{"id": str(row.id), "name": row.name, "country_code": row.country_code} for row in rows]

@router.post("/institutions/suggest", status_code=201)
async def suggest_institution(data: InstitutionSuggestion, current_user: RequireTutor, db: DBSession):
    result = await BackgroundService(db).suggest_institution(current_user, data.name, data.country_code)
    await db.commit()
    return result

@router.post("/background/documents", status_code=201)
async def upload_background_document(current_user: RequireTutor, db: DBSession, file: Annotated[UploadFile, File(...)]):
    from app.core.cloudinary_service import upload_tutor_background_document
    from app.core.config import settings
    from app.core.cloudinary_service import ALLOWED_IDENTITY_DOCUMENT_TYPES
    if file.content_type not in ALLOWED_IDENTITY_DOCUMENT_TYPES:
        raise HTTPException(415, "Upload a PDF, JPEG, or PNG document.")
    content = await file.read(settings.CLOUDINARY_IDENTITY_DOCUMENT_MAX_SIZE + 1)
    if not content:
        raise HTTPException(422, "The uploaded document is empty.")
    if len(content) > settings.CLOUDINARY_IDENTITY_DOCUMENT_MAX_SIZE:
        raise HTTPException(413, "Document must not exceed 10 MB.")
    uploaded = upload_tutor_background_document(content, str(current_user.id), file.content_type)
    return {"public_id": uploaded["public_id"], "file_name": file.filename or "Document", "format": uploaded["format"]}


class InstitutionReview(BaseModel):
    status: str = Field(pattern="^(APPROVED|REJECTED)$")

@router.get("/admin/institutions/suggestions")
async def list_institution_suggestions(current_user: RequireAnyAdmin, db: DBSession):
    from app.domain.tutor_background.models.background import Institution
    rows = (await db.scalars(select(Institution).where(Institution.status == "PENDING").order_by(Institution.created_at))).all()
    return [{"id": str(row.id), "name": row.name, "country_code": row.country_code, "suggested_by_user_id": str(row.suggested_by_user_id) if row.suggested_by_user_id else None, "created_at": row.created_at} for row in rows]

@router.patch("/admin/institutions/{institution_id}")
async def review_institution_suggestion(institution_id: str, data: InstitutionReview, current_user: RequireAnyAdmin, db: DBSession):
    import uuid
    from app.domain.tutor_background.models.background import Institution
    try: parsed_id = uuid.UUID(institution_id)
    except ValueError: raise HTTPException(400, "Invalid institution ID.")
    item = await db.get(Institution, parsed_id)
    if not item: raise HTTPException(404, "Institution suggestion not found.")
    if item.status != "PENDING": raise HTTPException(409, "This institution suggestion has already been reviewed.")
    item.status = data.status
    await db.commit()
    return {"id": str(item.id), "name": item.name, "country_code": item.country_code, "status": item.status}


@router.get("/admin/background-documents/{record_type}/{record_id}")
async def get_background_document_download(record_type: str, record_id: str, current_user: RequireAnyAdmin, db: DBSession):
    import uuid
    from app.domain.tutor_background.models.background import TutorEducation, TutorCertification
    from app.core.cloudinary_service import get_tutor_background_document_download_url
    models = {"education": TutorEducation, "certification": TutorCertification}
    model = models.get(record_type)
    if model is None:
        raise HTTPException(404, "Background document not found.")
    try:
        parsed_id = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "Invalid background record ID.")
    record = await db.get(model, parsed_id)
    if not record or not record.document_public_id or not record.document_format:
        raise HTTPException(404, "Background document not found.")
    from app.core.config import settings
    return {
        "download_url": get_tutor_background_document_download_url(record.document_public_id, record.document_format),
        "expires_in_seconds": settings.CLOUDINARY_IDENTITY_DOCUMENT_URL_TTL_SECONDS,
    }


@router.get("/draft")
async def get_tutor_onboarding_draft(current_user: RequireTutor, db: DBSession):
    from app.domain.tutor_background.models.background import TutorOnboardingDraft
    from sqlalchemy import select
    draft = await db.scalar(
        select(TutorOnboardingDraft).where(
            TutorOnboardingDraft.tutor_user_id == current_user.id
        )
    )
    if draft is None:
        return {"payload": {}, "updated_at": None}
    return {"payload": draft.payload, "updated_at": draft.updated_at}


@router.put("/draft")
async def save_tutor_onboarding_draft(
    payload: dict,
    current_user: RequireTutor,
    db: DBSession,
):
    from app.domain.tutor_background.models.background import TutorOnboardingDraft
    from sqlalchemy import select
    draft = await db.scalar(
        select(TutorOnboardingDraft)
        .where(TutorOnboardingDraft.tutor_user_id == current_user.id)
        .with_for_update()
    )
    if draft is None:
        draft = TutorOnboardingDraft(
            tutor_user_id=current_user.id,
            payload=payload,
        )
        db.add(draft)
    else:
        draft.payload = payload
    await db.commit()
    await db.refresh(draft)
    return {"saved": True, "updated_at": draft.updated_at}


@router.delete("/draft", status_code=204)
async def delete_tutor_onboarding_draft(current_user: RequireTutor, db: DBSession):
    from app.domain.tutor_background.models.background import TutorOnboardingDraft
    from sqlalchemy import delete
    await db.execute(
        delete(TutorOnboardingDraft).where(
            TutorOnboardingDraft.tutor_user_id == current_user.id
        )
    )
    await db.commit()
    return None


@router.get("/admin/verification/{verification_id}/background")
async def get_admin_tutor_background(
    verification_id: str,
    current_user: RequireAnyAdmin,
    db: DBSession,
):
    import uuid
    from app.domain.verification.models.tutor_verification import TutorVerification
    from app.domain.tutors.repositories.tutor_repository import TutorRepository
    from app.domain.tutor_background.models.background import (
        TutorEducation, TutorCertification, TutorWorkHistory,
    )
    try:
        parsed_id = uuid.UUID(verification_id)
    except ValueError:
        raise HTTPException(400, "Invalid verification ID.")
    verification = await db.get(TutorVerification, parsed_id)
    if verification is None:
        raise HTTPException(404, "Verification record not found.")
    profile = await TutorRepository(db).get_by_user_id(verification.tutor_user_id)
    if profile is None:
        return {"education": [], "certifications": [], "work_history": []}
    education = (await db.scalars(select(TutorEducation).where(TutorEducation.tutor_profile_id == profile.id).order_by(TutorEducation.start_date))).all()
    certifications = (await db.scalars(select(TutorCertification).where(TutorCertification.tutor_profile_id == profile.id).order_by(TutorCertification.created_at))).all()
    work_history = (await db.scalars(select(TutorWorkHistory).where(TutorWorkHistory.tutor_profile_id == profile.id).order_by(TutorWorkHistory.start_date))).all()
    def public_record(row):
        return {
            key: value for key, value in row.__dict__.items()
            if not key.startswith("_") and key not in {"document_public_id"}
        }
    return {
        "education": [public_record(row) for row in education],
        "certifications": [public_record(row) for row in certifications],
        "work_history": [public_record(row) for row in work_history],
    }
