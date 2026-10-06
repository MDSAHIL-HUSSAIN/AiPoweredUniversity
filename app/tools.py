import time
from typing import Dict, Any, List, Optional
from app import database

class DeterministicTools:
    """
    Rule R5 Deterministic Tools:
    Executes SQLite lookups and strict mathematical/eligibility rules.
    Never relies on LLM arithmetic or judgement.
    """

    @classmethod
    def get_attendance(cls, student_id: str, course_code: Optional[str] = None) -> Dict[str, Any]:
        """Fetches student attendance record and calculates percentage."""
        t0 = time.time()
        records = database.get_attendance(student_id, course_code)
        latency_ms = int((time.time() - t0) * 1000)

        if not records:
            return {
                "tool": "get_attendance",
                "status": "not_found",
                "ms": latency_ms,
                "input": {"student_id": student_id, "course_code": course_code},
                "output": {"error": f"No attendance record found for student {student_id}"}
            }

        first = records[0]
        output = {
            "student_id": student_id,
            "course_code": first["course_code"],
            "course_name": first["course_name"],
            "classes_held": first["classes_held"],
            "classes_attended": first["classes_attended"],
            "attendance_pct": first["attendance_pct"]
        }

        return {
            "tool": "get_attendance",
            "status": "ok",
            "ms": max(1, latency_ms),
            "input": {"student_id": student_id, "course_code": course_code},
            "output": output
        }

    @classmethod
    def check_exam_eligibility(
        cls,
        student_id: str,
        course_code: str,
        min_required_pct: float = 75.0,
        applied_rule_id: str = "ATT-MIN-01"
    ) -> Dict[str, Any]:
        """Checks end-sem exam eligibility based on attendance threshold."""
        t0 = time.time()
        att_res = cls.get_attendance(student_id, course_code)
        latency_ms = int((time.time() - t0) * 1000)

        if att_res["status"] != "ok":
            return {
                "tool": "check_exam_eligibility",
                "status": "error",
                "ms": latency_ms,
                "input": {"student_id": student_id, "course_code": course_code, "min_required_pct": min_required_pct},
                "output": {"result": "INELIGIBLE", "reason": "No attendance record found"}
            }

        att_pct = att_res["output"]["attendance_pct"]
        is_eligible = att_pct >= min_required_pct
        result_str = "ELIGIBLE" if is_eligible else "NOT_ELIGIBLE"

        return {
            "tool": "check_exam_eligibility",
            "status": "ok",
            "ms": max(1, latency_ms),
            "input": {"student_id": student_id, "course_code": course_code, "min_required_pct": min_required_pct},
            "output": {
                "result": result_str,
                "rule_id": applied_rule_id,
                "attendance_pct": att_pct,
                "required_pct": min_required_pct
            }
        }

    @classmethod
    def check_supp_eligibility(cls, student_id: str, course_code: str) -> Dict[str, Any]:
        """Checks supplementary exam eligibility (requires attendance >= 75% AND exam result FAIL)."""
        t0 = time.time()
        att_res = cls.get_attendance(student_id, course_code)
        results = database.get_results(student_id, course_code)
        latency_ms = int((time.time() - t0) * 1000)

        if att_res["status"] != "ok" or not results:
            return {
                "tool": "check_supp_eligibility",
                "status": "error",
                "ms": latency_ms,
                "input": {"student_id": student_id, "course_code": course_code},
                "output": {"result": "INELIGIBLE", "reason": "Missing course attendance or result record"}
            }

        att_pct = att_res["output"]["attendance_pct"]
        latest_res = results[0]
        exam_result = latest_res["result"]

        is_eligible = (att_pct >= 75.0) and (exam_result == "FAIL")
        
        reason = ""
        if exam_result == "PASS":
            reason = "Student has already passed the course."
        elif exam_result == "DETAINED":
            reason = "Student was detained due to low attendance and must re-register."
        elif att_pct < 75.0:
            reason = f"Attendance is {att_pct}%, which is below the 75% minimum required for supplementary exam."
        else:
            reason = "Eligible: Failed regular exam with valid attendance."

        return {
            "tool": "check_supp_eligibility",
            "status": "ok",
            "ms": max(1, latency_ms),
            "input": {"student_id": student_id, "course_code": course_code},
            "output": {
                "result": "ELIGIBLE" if is_eligible else "INELIGIBLE",
                "rule_id": "SUPP-ELIG-01",
                "attendance_pct": att_pct,
                "exam_result": exam_result,
                "reason": reason
            }
        }

    @classmethod
    def check_placement_eligibility(cls, student_id: str) -> Dict[str, Any]:
        """Checks placement eligibility against CGPA >= 6.5 and active backlogs <= 0."""
        t0 = time.time()
        student = database.get_student(student_id)
        latency_ms = int((time.time() - t0) * 1000)

        if not student:
            return {
                "tool": "check_placement_eligibility",
                "status": "error",
                "ms": latency_ms,
                "input": {"student_id": student_id},
                "output": {"result": "INELIGIBLE", "reason": "Student record not found"}
            }

        cgpa = student["cgpa"]
        backlogs = student["active_backlogs"]

        cgpa_ok = cgpa >= 6.50
        backlogs_ok = backlogs == 0
        is_eligible = cgpa_ok and backlogs_ok

        reasons = []
        if not cgpa_ok:
            reasons.append(f"CGPA {cgpa} is below minimum requirement of 6.50 (Clause 3.1)")
        if not backlogs_ok:
            reasons.append(f"Student has {backlogs} active backlog(s); 0 allowed (Clause 3.2)")

        return {
            "tool": "check_placement_eligibility",
            "status": "ok",
            "ms": max(1, latency_ms),
            "input": {"student_id": student_id},
            "output": {
                "result": "ELIGIBLE" if is_eligible else "INELIGIBLE",
                "cgpa": cgpa,
                "active_backlogs": backlogs,
                "rules_applied": ["PLACEMENT-CGPA-01", "PLACEMENT-BACKLOG-01"],
                "reasons": reasons if reasons else ["Meets CGPA and backlog requirements"]
            }
        }
