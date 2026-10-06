from app.repositories.rule_repository import session_date


def result_order(r):
    # supplementary of the same session date counts as later than the regular one
    d = session_date(r["exam_session"]) or "0000-00-00"
    if str(r["exam_type"]).upper() == "SUPPLEMENTARY":
        return d + "-2"
    return d + "-1"


class StudentRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_student(self, student_id):
        row = self.conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def courses_for(self, programme):
        rows = self.conn.execute("SELECT * FROM courses WHERE programme = ? ORDER BY course_code",
                                 (programme,)).fetchall()
        out = []
        for r in rows:
            out.append(dict(r))
        return out

    def find_course(self, student, text):
        # exact code, then exact name, then a unique partial name match within the student's programme
        if text is None or str(text).strip() == "":
            return None
        t = str(text).strip().lower()
        row = self.conn.execute("SELECT * FROM courses WHERE lower(course_code) = ?", (t,)).fetchone()
        if row is not None:
            return dict(row)
        courses = self.courses_for(student["programme"])
        for c in courses:
            if c["course_name"].lower() == t:
                return c
        matches = []
        for c in courses:
            if t in c["course_name"].lower():
                matches.append(c)
        if len(matches) == 1:
            return matches[0]
        return None

    def attendance(self, student_id, course_code=None):
        q = ("SELECT a.*, c.course_name FROM attendance a JOIN courses c ON a.course_code = c.course_code "
             "WHERE a.student_id = ?")
        params = [student_id]
        if course_code:
            q += " AND a.course_code = ?"
            params.append(course_code)
        rows = self.conn.execute(q + " ORDER BY a.course_code", params).fetchall()
        out = []
        for r in rows:
            out.append(dict(r))
        return out

    def results(self, student_id, course_code=None):
        q = "SELECT * FROM results WHERE student_id = ?"
        params = [student_id]
        if course_code:
            q += " AND course_code = ?"
            params.append(course_code)
        out = []
        for r in self.conn.execute(q, params).fetchall():
            out.append(dict(r))
        out.sort(key=lambda x: (x["course_code"], result_order(x)))
        return out

    def latest_result(self, student_id, course_code):
        rows = self.results(student_id, course_code)
        if len(rows) == 0:
            return None
        rows.sort(key=result_order)
        return rows[-1]
