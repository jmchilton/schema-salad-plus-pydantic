"""Shared test fixtures for schema-salad-plus-pydantic tests."""

from __future__ import annotations

import os
from io import StringIO
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
SCHEMAS_DIR = TESTS_DIR / "schemas"
SIMPLE_SCHEMA = SCHEMAS_DIR / "simple.yml"

GXFORMAT2_SCHEMA_DIR = os.environ.get(
    "GXFORMAT2_SCHEMA_DIR",
    str(Path(__file__).parent.parent.parent.parent / "worktrees" / "gxformat2" / "branch" / "doc_fixes" / "schema"),
)
NATIVE_SCHEMA = os.path.join(GXFORMAT2_SCHEMA_DIR, "native_v0_1", "workflow.yml")
GXFORMAT2_TESTS_DIR = os.path.join(os.path.dirname(GXFORMAT2_SCHEMA_DIR), "tests")


@pytest.fixture
def simple_schema_path() -> Path:
    return SIMPLE_SCHEMA


@pytest.fixture
def generate_code_from_schema():
    """Factory fixture: generate pydantic code from a schema path, return the code string."""

    def _generate(schema_path: str | Path) -> str:
        from schema_salad_plus_pydantic.orchestrate import generate_from_schema

        buf = StringIO()
        generate_from_schema(str(schema_path), buf)
        return buf.getvalue()

    return _generate
