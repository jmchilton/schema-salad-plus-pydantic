"""Roundtrip tests: generate TypeScript -> tsc type-check -> node runtime assertions."""

from __future__ import annotations

import shutil
import subprocess
from io import StringIO
from pathlib import Path

import nodejs_wheel.executable as _nw
import pytest
from conftest import NATIVE_SCHEMA

TESTS_DIR = Path(__file__).parent
TS_PROJECT_SRC = TESTS_DIR / "ts_project"

_NODE = str(Path(_nw.ROOT_DIR) / "bin" / "node")
_NPM = [_NODE, str(Path(_nw.ROOT_DIR) / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js")]


_SCAFFOLDING = ("package.json", "tsconfig.json")


def _setup_ts_project(
    tmp_path_factory: pytest.TempPathFactory,
    name: str,
    schema_path: str,
    *,
    copy_validation_scripts: bool = False,
) -> Path:
    """Copy ts_project scaffolding to a temp dir, generate code, npm install."""
    project = tmp_path_factory.mktemp(name)
    for f in TS_PROJECT_SRC.iterdir():
        if f.name in _SCAFFOLDING or (copy_validation_scripts and f.suffix == ".ts"):
            shutil.copy2(f, project / f.name)

    from schema_salad_plus_pydantic.orchestrate import generate_from_schema

    buf = StringIO()
    generate_from_schema(schema_path, buf, output_format="typescript")
    (project / "generated.ts").write_text(buf.getvalue())

    result = subprocess.run(
        [*_NPM, "install", "--prefix", str(project)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"npm install failed:\n{result.stderr}"

    return project


@pytest.fixture(scope="session")
def ts_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Simple schema ts_project with validation scripts."""
    return _setup_ts_project(
        tmp_path_factory, "ts_project", str(TESTS_DIR / "schemas" / "simple.yml"), copy_validation_scripts=True
    )


@pytest.fixture(scope="session")
def ts_project_native(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """gxformat2 native schema ts_project (compile-only, no validation scripts)."""
    return _setup_ts_project(tmp_path_factory, "ts_project_native", NATIVE_SCHEMA)


def _tsc(project: Path) -> subprocess.CompletedProcess[str]:
    """Run tsc --noEmit in the project directory."""
    return subprocess.run(
        [
            _NODE,
            str(project / "node_modules" / ".bin" / "tsc"),
            "--noEmit",
            "--project",
            str(project / "tsconfig.json"),
        ],
        capture_output=True,
        text=True,
    )


def _node(script: Path) -> subprocess.CompletedProcess[str]:
    """Run a .ts script with node."""
    return subprocess.run([_NODE, str(script)], capture_output=True, text=True)


class TestTypeScriptRoundtrip:
    """Test generated TypeScript via tsc and node."""

    def test_tsc_type_checks_pass(self, ts_project: Path) -> None:
        """tsc --noEmit succeeds: good data compiles, @ts-expect-error proves bad data is caught."""
        result = _tsc(ts_project)
        assert result.returncode == 0, f"tsc failed:\n{result.stdout}\n{result.stderr}"

    def test_runtime_assertions(self, ts_project: Path) -> None:
        """node runs validate_good.ts and all runtime assertions pass."""
        result = _node(ts_project / "validate_good.ts")
        assert result.returncode == 0, f"Runtime validation failed:\n{result.stdout}\n{result.stderr}"

    def test_generated_code_is_nonempty(self, ts_project: Path) -> None:
        """Sanity: generated.ts was actually written."""
        code = (ts_project / "generated.ts").read_text()
        assert "export interface" in code
        assert len(code) > 200


@pytest.mark.skipif(not Path(NATIVE_SCHEMA).exists(), reason="gxformat2 schema not available")
class TestNativeSchemaTypeScript:
    """Test generated TypeScript for gxformat2 native schema compiles."""

    def test_tsc_compiles(self, ts_project_native: Path) -> None:
        """tsc --noEmit succeeds on generated code from the native gxformat2 schema."""
        result = _tsc(ts_project_native)
        assert result.returncode == 0, f"tsc failed:\n{result.stdout}\n{result.stderr}"
