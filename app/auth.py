import re
from typing import Optional, Tuple, Dict, Any

class AuthNode:
    """
    Auth Node enforcing Rule R7 (Authorisation and privacy) and Rule R8 (Untrusted content).
    - Identity comes ONLY from request context header 'X-Student-Id', NEVER from message text.
    - Refuses requests for another student's data (answer_type: 'refused').
    - Requires header X-Student-Id for personal data/eligibility queries.
    """
    
    PERSONAL_DATA_KEYWORDS = [
        "my attendance", "my marks", "my cgpa", "my backlogs", "my result", "my eligibility",
        "am i eligible", "what is my", "can i appear", "have i passed", "my score",
        "attendance in", "marks in", "eligible for", "backlog", "backlogs"
    ]
    
    STUDENT_ID_REGEX = re.compile(r'\b(S\d{4})\b', re.IGNORECASE)
    INJECTION_REGEX = re.compile(
        r'(ignore (all )?previous instructions|system prompt|override security|disregard prior|you are now|jailbreak)',
        re.IGNORECASE
    )

    @classmethod
    def extract_student_id(cls, headers: Dict[str, str]) -> Optional[str]:
        """Extract X-Student-Id from HTTP headers (case-insensitive)."""
        for k, v in headers.items():
            if k.lower() == "x-student-id" and v and v.strip():
                return v.strip()
        return None

    @classmethod
    def evaluate(cls, question: str, header_student_id: Optional[str]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Evaluates authorization and security policies.
        Returns:
            (is_allowed: bool, answer_type: str, refusal_message: str, target_student_id: str)
        """
        q_lower = question.lower()
        
        # 1. Untrusted Prompt Injection Guard (R8)
        if cls.INJECTION_REGEX.search(question):
            return (
                False,
                "refused",
                "Request refused: Untrusted content or instruction override attempt detected in question text.",
                header_student_id
            )

        # 2. Check for student IDs embedded in question text
        embedded_student_ids = cls.STUDENT_ID_REGEX.findall(question)
        if embedded_student_ids:
            target_id = embedded_student_ids[0].upper()
            
            # Rule R7: Cannot request another student's data
            if not header_student_id:
                return (
                    False,
                    "refused",
                    f"Request refused: Query mentions student '{target_id}' but no authenticated X-Student-Id header was provided.",
                    None
                )
            
            if header_student_id.upper() != target_id:
                return (
                    False,
                    "refused",
                    f"Request refused: You are authenticated as '{header_student_id.upper()}' and cannot access records for student '{target_id}'.",
                    header_student_id
                )

        # 3. Check for personal data / eligibility intent
        is_personal_intent = any(kw in q_lower for kw in cls.PERSONAL_DATA_KEYWORDS)
        
        if is_personal_intent and not header_student_id:
            return (
                False,
                "refused",
                "Request refused: Personal student data and eligibility checks require an authenticated student identity in the X-Student-Id header.",
                None
            )

        # If personal intent and valid header present, target is header_student_id
        target_student_id = header_student_id if is_personal_intent else (header_student_id or None)
        return (True, None, None, target_student_id)