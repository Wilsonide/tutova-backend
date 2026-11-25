from fastapi import HTTPException
from sqlalchemy import select, delete, func
from app.domain.tutors.models.tutor_profile import TutorProfile
from app.domain.tutor_background.models.background import Institution, TutorEducation, TutorCertification, TutorWorkHistory
from app.domain.tutor_background.repositories.background_repository import BackgroundRepository
from app.domain.tutor_background.schemas.background import BackgroundReplace

class BackgroundService:
    def __init__(self, db): self.db = db; self.repo = BackgroundRepository(db)
    async def profile(self, user):
        profile = await self.db.scalar(select(TutorProfile).where(TutorProfile.user_id == user.id))
        if not profile: raise HTTPException(409, "Create your tutor profile before adding education or experience.")
        return profile
    async def list(self, user):
        p = await self.profile(user)
        groups = [TutorEducation, TutorCertification, TutorWorkHistory]
        rows = [list((await self.db.scalars(select(m).where(m.tutor_profile_id == p.id).order_by(m.created_at))).all()) for m in groups]
        return {"education": rows[0], "certifications": rows[1], "work_history": rows[2]}
    async def replace(self, user, data: BackgroundReplace):
        p = await self.profile(user)
        # Replace each category atomically; IDs are regenerated to prevent cross-tutor record reassignment.
        for model in (TutorEducation, TutorCertification, TutorWorkHistory):
            await self.db.execute(delete(model).where(model.tutor_profile_id == p.id))
        for item in data.education:
            values = item.model_dump(exclude={"id"})
            institution_id = values.get("institution_id")
            if institution_id:
                institution = await self.db.get(Institution, institution_id)
                if not institution or institution.status != "APPROVED":
                    raise HTTPException(400, "Selected institution is not available.")
            else:
                institution = await self.db.scalar(select(Institution).where(func.lower(Institution.name) == values["institution_name"].lower(), Institution.country_code == values["country_code"], Institution.status == "APPROVED"))
                if institution: values["institution_id"] = institution.id
            self.db.add(TutorEducation(tutor_profile_id=p.id, **values))
        for item in data.certifications: self.db.add(TutorCertification(tutor_profile_id=p.id, **item.model_dump(exclude={"id"})))
        for item in data.work_history: self.db.add(TutorWorkHistory(tutor_profile_id=p.id, **item.model_dump(exclude={"id"})))
        await self.db.flush()
        return await self.list(user)
    async def suggest_institution(self, user, name, country_code):
        name = name.strip()
        existing = await self.db.scalar(select(Institution).where(func.lower(Institution.name) == name.lower(), Institution.country_code == country_code.upper()))
        if existing: return {"id": str(existing.id), "name": existing.name, "country_code": existing.country_code, "status": existing.status, "message": "Institution already exists."}
        item = Institution(name=name, country_code=country_code.upper(), status="PENDING", suggested_by_user_id=user.id)
        self.db.add(item); await self.db.flush()
        return {"id": str(item.id), "name": item.name, "country_code": item.country_code, "status": item.status, "message": "Institution suggestion submitted for review."}
    async def search_institutions(self, query, country_code):
        return await self.repo.institutions(query, country_code)
