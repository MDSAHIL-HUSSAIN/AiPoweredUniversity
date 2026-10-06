"""Production authorization policy for trusted request-header identity."""

import re

from app.contracts import AuthorizationResult


_STUDENT_ID = re.compile(r"\bS\d{4,}\b", re.IGNORECASE)
_INJECTION = re.compile(
    r"ignore (?:all )?previous instructions|system prompt|override security|"
    r"disregard prior|you are now|jailbreak",
    re.IGNORECASE,
)


class HeaderAuthorizer:
    """Enforce privacy without deriving identity from question text."""

    def authorize(
        self,
        student_id: str | None,
        question_category: str,
        question: str = "",
    ) -> AuthorizationResult:
        if _INJECTION.search(question):
            return AuthorizationResult(
                allowed=False,
                reason="Request refused because it contains an instruction-override attempt.",
            )

        personal = {"personal_data", "eligibility", "multi_step"}
        if question_category in personal and not student_id:
            return AuthorizationResult(
                allowed=False,
                reason="X-Student-ID is required for personal questions.",
            )

        trusted_id = student_id.upper() if student_id else None
        mentioned_ids = {value.upper() for value in _STUDENT_ID.findall(question)}
        if question_category in personal and any(
            value != trusted_id for value in mentioned_ids
        ):
            return AuthorizationResult(
                allowed=False,
                reason="Requests for another student's personal data are not allowed.",
            )
        return AuthorizationResult(allowed=True)
