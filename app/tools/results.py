from app.tools.common import done, fail, resolve_course, NOT_FOUND

NAME = "get_results"


def get_results(students, student_id, course_code=None):
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

    rows = students.results(student_id, code)
    return done(NAME, inputs, {
        "student_id": student_id,
        "programme": st["programme"],
        "batch_year": st["batch_year"],
        "current_semester": st["current_semester"],
        "cgpa": st["cgpa"],
        "active_backlogs": st["active_backlogs"],
        "results": rows,
    })
