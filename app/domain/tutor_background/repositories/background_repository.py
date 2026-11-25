from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.tutor_background.models.background import Institution, TutorEducation, TutorCertification, TutorWorkHistory

class BackgroundRepository:
    def __init__(self, db: AsyncSession): self.db = db
    async def get_profile(self, profile_id):
        return await self.db.execute(select(TutorEducation).where(TutorEducation.tutor_profile_id == profile_id))
    async def institutions(self, query, country_code):
        stmt = select(Institution).where(Institution.status == "APPROVED", func.lower(Institution.name).contains(query.lower()))
        if country_code: stmt = stmt.where(Institution.country_code == country_code.upper())
        return list((await self.db.scalars(stmt.order_by(Institution.name).limit(20))).all())
