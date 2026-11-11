from app.domain.verification.models.tutor_verification import ApplicationStatus


def test_application_workflow_has_expected_terminal_states():
    assert ApplicationStatus.APPROVED.value == "APPROVED"
    assert ApplicationStatus.REJECTED.value == "REJECTED"
    assert (
        ApplicationStatus.ADDITIONAL_INFO_REQUIRED.value == "ADDITIONAL_INFO_REQUIRED"
    )
