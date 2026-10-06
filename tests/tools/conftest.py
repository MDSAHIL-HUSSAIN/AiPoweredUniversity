import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

from scripts.seed_test_db import build_test_conn
from app.tools import UniversityTools


@pytest.fixture
def conn():
    c, _ = build_test_conn(":memory:")
    return c


@pytest.fixture
def tools(conn):
    return UniversityTools(conn)
