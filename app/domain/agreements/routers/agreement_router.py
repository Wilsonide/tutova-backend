import uuid
from fastapi import APIRouter
from app.core.dependencies import CurrentUser, DBSession, RequireTutor, RequireRequester
from app.domain.agreements.schemas.agreement import AgreementChangeRequest, AgreementLearnerDecision, AgreementResponse
from app.domain.agreements.services.agreement_service import AgreementService

router=APIRouter(prefix="/agreements",tags=["Tutoring Agreements"])

@router.get("/mine",response_model=list[AgreementResponse])
async def list_my_agreements(current_user:CurrentUser,db:DBSession):
    return await AgreementService(db).list_mine(current_user)

@router.post("/{agreement_id}/tutor-accept",response_model=AgreementResponse)
async def tutor_accept_agreement(agreement_id:uuid.UUID,current_user:RequireTutor,db:DBSession):
    return await AgreementService(db).tutor_accept(current_user,agreement_id)

@router.post("/{agreement_id}/tutor-request-changes",response_model=AgreementResponse)
async def tutor_request_agreement_changes(agreement_id:uuid.UUID,payload:AgreementChangeRequest,current_user:RequireTutor,db:DBSession):
    return await AgreementService(db).tutor_request_changes(current_user,agreement_id,payload)

@router.post("/{agreement_id}/learner-decision",response_model=AgreementResponse)
async def learner_decide_agreement(agreement_id:uuid.UUID,payload:AgreementLearnerDecision,current_user:RequireRequester,db:DBSession):
    return await AgreementService(db).learner_decide(current_user,agreement_id,payload)
