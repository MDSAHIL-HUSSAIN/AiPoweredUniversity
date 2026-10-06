from fractions import Fraction

from app.tools.common import done, fail, resolve_course, NOT_FOUND

NAME = "get_attendance"


def get_attendance(students, student_id, course_code=None):
    inputs = {"student_id": student_id, "course_code": course_code}
    st = students.get_student(student_id)
    if st is None:
        return fail(NAME, inputs, NOT_FOUND, "student not found")

    code = None
    if course_code:
        c, ask = resolve_course(students, NAME, inputs, st, course_code)
        if ask:
            return ask
        code = c["course_code"]

    rows = students.attendance(student_id, code)
    if len(rows) == 0:
        return fail(NAME, inputs, NOT_FOUND, "no attendance record found")

    out = []
    for r in rows:
        pct = Fraction(r["classes_attended"] * 100, r["classes_held"])
        out.append({
            "course_code": r["course_code"],
            "course_name": r["course_name"],
            "classes_held": r["classes_held"],
            "classes_attended": r["classes_attended"],
            "attendance_pct": round(float(pct), 2),
        })
    return done(NAME, inputs, {"student_id": student_id, "attendance": out})
