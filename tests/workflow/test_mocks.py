from datetime import date

from app.workflow.mocks import FakeAuthorizer, FakeUniversityTools


def test_authorizer_requires_identity_for_personal_question():
    result = FakeAuthorizer().authorize(None, "personal_data")
    assert result.allowed is False


def test_mock_tool_uses_consistent_contract():
    result = FakeUniversityTools().get_attendance("S1001", "CS201")
    assert result.success is True
    assert result.tool_name == "get_attendance"
    assert result.inputs == {"student_id": "S1001", "course_code": "CS201"}


def test_mock_eligibility_serializes_date():
    result = FakeUniversityTools().check_exam_eligibility(
        "S1001", "CS201", date(2026, 10, 6)
    )
    assert result.inputs["as_of_date"] == "2026-10-06"

