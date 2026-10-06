import os
import sqlite3

SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/runtime/university.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    programme TEXT NOT NULL,
    batch_year INTEGER NOT NULL,
    current_semester INTEGER NOT NULL,
    cgpa REAL NOT NULL,
    active_backlogs INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    programme TEXT NOT NULL,
    semester INTEGER,
    credits INTEGER
);

CREATE TABLE IF NOT EXISTS attendance (
    student_id TEXT NOT NULL REFERENCES students(student_id),
    course_code TEXT NOT NULL REFERENCES courses(course_code),
    classes_held INTEGER NOT NULL,
    classes_attended INTEGER NOT NULL,
    PRIMARY KEY (student_id, course_code)
);

CREATE TABLE IF NOT EXISTS results (
    student_id TEXT NOT NULL REFERENCES students(student_id),
    course_code TEXT NOT NULL REFERENCES courses(course_code),
    exam_session TEXT NOT NULL,
    exam_type TEXT NOT NULL,
    internal_marks INTEGER,
    external_marks INTEGER,
    total_marks INTEGER,
    max_marks INTEGER,
    result TEXT NOT NULL,
    PRIMARY KEY (student_id, course_code, exam_session, exam_type)
);

CREATE TABLE IF NOT EXISTS rule_registry (
    rule_id TEXT PRIMARY KEY,
    description TEXT,
    parameter TEXT NOT NULL,
    operator TEXT NOT NULL,
    value TEXT NOT NULL,
    scope_programmes TEXT DEFAULT 'ALL',
    scope_batches TEXT DEFAULT 'ALL',
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    source_doc_id TEXT NOT NULL,
    source_section TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    trace_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    student_id TEXT,
    record_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_register (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    issuer TEXT NOT NULL,
    authority_level INTEGER NOT NULL,
    doc_type TEXT NOT NULL,
    version TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    supersedes TEXT NOT NULL DEFAULT '[]',
    scope_programmes TEXT NOT NULL DEFAULT '["ALL"]',
    scope_batches TEXT NOT NULL DEFAULT '["ALL"]',
    provenance TEXT NOT NULL,
    retrieved_on TEXT NOT NULL,
    synthetic INTEGER NOT NULL DEFAULT 0
);
"""

TABLE_COLUMNS = {
    "courses": ["course_code", "course_name", "programme", "semester", "credits"],
    "students": ["student_id", "full_name", "programme", "batch_year", "current_semester", "cgpa", "active_backlogs"],
    "attendance": ["student_id", "course_code", "classes_held", "classes_attended"],
    "results": ["student_id", "course_code", "exam_session", "exam_type", "internal_marks",
                "external_marks", "total_marks", "max_marks", "result"],
}

TABLE_KEYS = {
    "courses": ["course_code"],
    "students": ["student_id"],
    "attendance": ["student_id", "course_code"],
    "results": ["student_id", "course_code", "exam_session", "exam_type"],
}


def get_conn(path=None):
    # creates the file + tables if needed. check_same_thread=False so FastAPI workers can share it
    if path is None:
        path = SQLITE_PATH
    folder = os.path.dirname(path)
    if folder != "" and path != ":memory:":
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


init_db = get_conn


def row_key(table, row):
    parts = []
    for k in TABLE_KEYS[table]:
        parts.append(str(row.get(k, "")).strip())
    return "|".join(parts)
