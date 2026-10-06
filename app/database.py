import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "university.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite database with Annex C tables and initial seed data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Students Table (Annex C)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        programme TEXT NOT NULL,
        batch_year INTEGER NOT NULL,
        current_semester INTEGER NOT NULL,
        cgpa REAL NOT NULL,
        active_backlogs INTEGER NOT NULL
    )
    """)

    # 2. Courses Table (Annex C)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        course_code TEXT PRIMARY KEY,
        course_name TEXT NOT NULL,
        programme TEXT NOT NULL,
        semester INTEGER NOT NULL,
        credits INTEGER NOT NULL
    )
    """)

    # 3. Attendance Table (Annex C)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        student_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        classes_held INTEGER NOT NULL,
        classes_attended INTEGER NOT NULL,
        PRIMARY KEY (student_id, course_code),
        FOREIGN KEY (student_id) REFERENCES students(student_id),
        FOREIGN KEY (course_code) REFERENCES courses(course_code)
    )
    """)

    # 4. Results Table (Annex C)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        student_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        exam_session TEXT NOT NULL,
        exam_type TEXT NOT NULL,
        internal_marks INTEGER NOT NULL,
        external_marks INTEGER NOT NULL,
        total_marks INTEGER NOT NULL,
        max_marks INTEGER NOT NULL,
        result TEXT NOT NULL,
        PRIMARY KEY (student_id, course_code, exam_session),
        FOREIGN KEY (student_id) REFERENCES students(student_id),
        FOREIGN KEY (course_code) REFERENCES courses(course_code)
    )
    """)

    # 5. Rule Registry Table (Annex C)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rule_registry (
        rule_id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        parameter TEXT NOT NULL,
        operator TEXT NOT NULL,
        value TEXT NOT NULL,
        scope_programmes TEXT NOT NULL,
        scope_batches TEXT NOT NULL,
        effective_from TEXT NOT NULL,
        effective_to TEXT,
        source_doc_id TEXT NOT NULL,
        source_section TEXT NOT NULL
    )
    """)

    # 6. Source Register Table (Annex B)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_register (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        issuer TEXT NOT NULL,
        authority_level INTEGER NOT NULL,
        doc_type TEXT NOT NULL,
        version TEXT NOT NULL,
        effective_from TEXT NOT NULL,
        effective_to TEXT,
        supersedes TEXT,
        scope_programmes TEXT NOT NULL,
        scope_batches TEXT NOT NULL,
        provenance TEXT,
        retrieved_on TEXT NOT NULL,
        synthetic TEXT NOT NULL
    )
    """)

    # 7. Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        trace_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        student_id TEXT,
        question TEXT NOT NULL,
        answer_type TEXT NOT NULL,
        record_json TEXT NOT NULL
    )
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn: sqlite3.Connection):
    """Seed initial synthetic students, courses, attendance, results, rules, and sources."""
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM students")
    if cursor.fetchone()[0] > 0:
        return

    # Seed Students
    students_data = [
        ("S1001", "Aarav Sharma", "B.Tech CSE", 2023, 5, 7.80, 0), # Threshold 77.5% attendance
        ("S1002", "Priya Verma", "B.Tech CSE", 2023, 5, 6.40, 1), # Failed course, 1 backlog
        ("S1003", "Rohan Gupta", "B.Tech ECE", 2022, 7, 8.20, 0), # Placement eligible
        ("S1004", "Ananya Singh", "B.Tech ECE", 2023, 5, 5.10, 3), # Detained, low attendance
        ("S1005", "Kabir Patel", "B.Tech ME", 2024, 3, 7.10, 0),
        ("S1006", "Sneha Iyer", "B.Tech CSE", 2023, 5, 9.20, 0), # Top performer
        ("S1007", "Vikram Reddy", "B.Tech CSE", 2023, 5, 7.45, 0), # Attendance exact threshold 75%
        ("S1008", "Diya Mehta", "B.Tech ECE", 2023, 5, 7.00, 1),
    ]
    cursor.executemany(
        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?)", students_data
    )

    # Seed Courses
    courses_data = [
        ("CS201", "Data Structures & Algorithms", "B.Tech CSE", 5, 4),
        ("CS202", "Operating Systems", "B.Tech CSE", 5, 4),
        ("EC201", "Digital Electronics", "B.Tech ECE", 5, 4),
        ("MA101", "Engineering Mathematics I", "ALL", 1, 4),
    ]
    cursor.executemany(
        "INSERT INTO courses VALUES (?, ?, ?, ?, ?)", courses_data
    )

    # Seed Attendance
    attendance_data = [
        ("S1001", "CS201", 40, 31), # 77.5%
        ("S1001", "CS202", 40, 34), # 85.0%
        ("S1002", "CS201", 40, 28), # 70.0% (Below 75%)
        ("S1002", "MA101", 40, 32), # 80.0%
        ("S1003", "EC201", 45, 40), # 88.8%
        ("S1004", "EC201", 45, 20), # 44.4% (Detained)
        ("S1007", "CS201", 40, 30), # 75.0% (Exact threshold)
    ]
    cursor.executemany(
        "INSERT INTO attendance VALUES (?, ?, ?, ?)", attendance_data
    )

    # Seed Results
    results_data = [
        ("S1001", "CS201", "2026-MAY", "REGULAR", 35, 42, 77, 100, "PASS"),
        ("S1002", "CS201", "2026-MAY", "REGULAR", 15, 20, 35, 100, "FAIL"),
        ("S1003", "EC201", "2026-MAY", "REGULAR", 38, 48, 86, 100, "PASS"),
        ("S1004", "EC201", "2026-MAY", "REGULAR", 10, 15, 25, 100, "DETAINED"),
    ]
    cursor.executemany(
        "INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", results_data
    )

    # Seed Rule Registry
    rules_data = [
        ("ATT-MIN-01", "Minimum attendance required for regular end-sem examination", "min_attendance_pct", ">=", "75", "ALL", "ALL", "2024-07-01", "", "ACAD-REG-2024", "7.2"),
        ("ATT-COND-01", "Condonation of attendance shortfall up to 10% on medical grounds", "condonation_max_pct", "<=", "10", "ALL", "ALL", "2024-07-01", "", "ACAD-REG-2024", "7.3"),
        ("SUPP-ELIG-01", "Eligibility for supplementary examination if failed in regular exam with attendance >= 75%", "supp_exam_eligibility", "requires", "attendance>=75 AND result=FAIL", "ALL", "ALL", "2024-07-01", "", "ACAD-REG-2024", "9.1"),
        ("PLACEMENT-CGPA-01", "Minimum CGPA required for campus placement drive participation", "min_cgpa", ">=", "6.5", "B.Tech CSE;B.Tech ECE", "2022+;2023+", "2025-01-01", "", "PLACEMENT-POLICY-2025", "3.1"),
        ("PLACEMENT-BACKLOG-01", "Maximum active backlogs allowed for campus placements", "max_backlogs", "<=", "0", "ALL", "ALL", "2025-01-01", "", "PLACEMENT-POLICY-2025", "3.2"),
        ("SUPERSING-CIRCULAR-01", "Special Attendance Condonation Circular 2026", "min_attendance_pct", ">=", "70", "B.Tech CSE", "2023+", "2026-08-01", "", "ACAD-2026-08", "1")
    ]
    cursor.executemany(
        "INSERT INTO rule_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rules_data
    )

    # Seed Source Register (Annex B)
    sources_data = [
        ("ACAD-REG-2024", "Academic Regulations for B.Tech Programmes", "Office of Dean (Academics)", 1, "regulation", "3.1", "2024-07-01", "", "", "ALL", "ALL", "https://nsut.ac.in/regulations/2024", "2026-10-01", "N"),
        ("ACAD-2026-08", "Circular on Special Attendance Allowance for 2023 Batch", "Dean (Academics)", 2, "circular", "1.0", "2026-08-01", "", "ACAD-REG-2024#7.2", "B.Tech CSE", "2023+", "https://nsut.ac.in/circulars/2026-08", "2026-10-05", "Y"),
        ("PLACEMENT-POLICY-2025", "Training and Placement Policy 2025-26", "Training & Placement Cell", 2, "policy", "2.0", "2025-01-01", "", "", "ALL", "ALL", "https://nsut.ac.in/tnp/policy2025", "2026-10-01", "N")
    ]
    cursor.executemany(
        "INSERT INTO source_register VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sources_data
    )

    conn.commit()

# Query Helper Functions

def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id.upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_attendance(student_id: str, course_code: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if course_code:
        cursor.execute(
            "SELECT a.*, c.course_name FROM attendance a JOIN courses c ON a.course_code = c.course_code WHERE a.student_id = ? AND a.course_code = ?",
            (student_id.upper(), course_code.upper())
        )
    else:
        cursor.execute(
            "SELECT a.*, c.course_name FROM attendance a JOIN courses c ON a.course_code = c.course_code WHERE a.student_id = ?",
            (student_id.upper(),)
        )
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["attendance_pct"] = round((d["classes_attended"] / d["classes_held"]) * 100, 2) if d["classes_held"] > 0 else 0
        results.append(d)
    return results

def get_results(student_id: str, course_code: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if course_code:
        cursor.execute("SELECT * FROM results WHERE student_id = ? AND course_code = ?", (student_id.upper(), course_code.upper()))
    else:
        cursor.execute("SELECT * FROM results WHERE student_id = ?", (student_id.upper(),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_rules() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rule_registry")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_source_register() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_register")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_source_register_item(item: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO source_register VALUES (
        :doc_id, :title, :issuer, :authority_level, :doc_type, :version,
        :effective_from, :effective_to, :supersedes, :scope_programmes,
        :scope_batches, :provenance, :retrieved_on, :synthetic
    )
    """, item)
    conn.commit()
    conn.close()

def save_audit_record(trace_id: str, timestamp: str, student_id: Optional[str], question: str, answer_type: str, record_json: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO audit_logs VALUES (?, ?, ?, ?, ?, ?)",
        (trace_id, timestamp, student_id, question, answer_type, record_json)
    )
    conn.commit()
    conn.close()
