"""Roundtrip tests: generate models -> import -> validate real data."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from conftest import GXFORMAT2_TESTS_DIR, NATIVE_SCHEMA

BASIC_GA = Path(GXFORMAT2_TESTS_DIR) / "examples" / "native" / "basic.ga"


def _load_generated_module(code: str, module_name: str = "generated_models"):
    """Dynamically compile and import generated code as a module."""
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(code, f"<{module_name}>", "exec"), mod.__dict__)
    sys.modules[module_name] = mod
    return mod


@pytest.fixture
def native_models(generate_code_from_schema):
    """Generate and import models from the native_v0_1 schema."""
    if not Path(NATIVE_SCHEMA).exists():
        pytest.skip(f"gxformat2 schema not found at {NATIVE_SCHEMA}")
    code = generate_code_from_schema(NATIVE_SCHEMA)
    return _load_generated_module(code, "native_v0_1_models")


class TestSimpleSchemaRoundtrip:
    """Test roundtrip with the simple test schema."""

    def test_simple_model_validates(self, generate_code_from_schema, simple_schema_path):
        code = generate_code_from_schema(simple_schema_path)
        mod = _load_generated_module(code, "simple_models")

        data = {
            "name": "test-item",
            "status": "active",
            "format-version": "1.0",
            "items": {"key1": "val1", "key2": "val2"},
            "tags": ["a", "b"],
        }
        obj = mod.ChildRecord.model_validate(data)
        assert obj.name == "test-item"
        assert obj.format_version == "1.0"
        assert obj.items == {"key1": "val1", "key2": "val2"}
        assert obj.tags == ["a", "b"]

    def test_simple_model_optional_fields(self, generate_code_from_schema, simple_schema_path):
        code = generate_code_from_schema(simple_schema_path)
        mod = _load_generated_module(code, "simple_models_opt")

        # Minimal data — all optional fields omitted
        data = {}
        obj = mod.ChildRecord.model_validate(data)
        assert obj.tags is None


@pytest.mark.skipif(not Path(NATIVE_SCHEMA).exists(), reason="gxformat2 schema not available")
class TestNativeSchemaRoundtrip:
    """Test roundtrip with gxformat2 native_v0_1 schema."""

    def test_generates_valid_code(self, generate_code_from_schema):
        code = generate_code_from_schema(NATIVE_SCHEMA)
        compile(code, "<native_v0_1>", "exec")

    def test_expected_classes(self, native_models):
        for cls_name in [
            "NativeGalaxyWorkflow",
            "NativeStep",
            "NativeStepInput",
            "NativeStepOutput",
            "NativeReport",
            "NativeCreatorPerson",
            "NativeCreatorOrganization",
            "NativeSourceMetadata",
            "StepPosition",
            "ToolShedRepository",
        ]:
            assert hasattr(native_models, cls_name), f"Missing class {cls_name}"

    def test_expected_enums(self, native_models):
        assert hasattr(native_models, "NativeStepType")
        st = native_models.NativeStepType
        assert st.tool.value == "tool"
        assert st.data_input.value == "data_input"

    def test_minimal_workflow(self, native_models):
        data = {
            "a_galaxy_workflow": "true",
            "format-version": "0.1",
            "name": "Test Workflow",
        }
        wf = native_models.NativeGalaxyWorkflow.model_validate(data)
        assert wf.a_galaxy_workflow == "true"
        assert wf.format_version == "0.1"
        assert wf.name == "Test Workflow"

    def test_basic_ga_file(self, native_models):
        """Validate a real .ga file after normalizing hyphenated keys to underscores.

        Real .ga files use 'format-version' but our schema defines 'format_version'.
        Schema-salad handles this via JSON-LD context; for pydantic we normalize.
        """
        if not BASIC_GA.exists():
            pytest.skip(f"basic.ga not found at {BASIC_GA}")
        with open(BASIC_GA) as f:
            data = json.load(f)
        wf = native_models.NativeGalaxyWorkflow.model_validate(data)
        assert wf.a_galaxy_workflow == "true"
        assert wf.format_version == "0.1"
        assert wf.name == "Simple workflow"
        assert wf.uuid == "f27dcdb2-d606-4202-9207-4a6eb0187f26"

    def test_inheritance(self, native_models):
        """NativeStep should inherit from HasUUID, HasStepErrors, etc."""
        step_cls = native_models.NativeStep
        # Check MRO contains parent classes
        mro_names = [c.__name__ for c in step_cls.__mro__]
        for parent in ["HasUUID", "HasStepErrors", "HasStepPosition", "ReferencesTool"]:
            assert parent in mro_names, f"NativeStep missing parent {parent}"

    def test_step_position(self, native_models):
        pos = native_models.StepPosition.model_validate({"top": 10.5, "left": 20.0})
        assert pos.top == 10.5
        assert pos.left == 20.0

    def test_extra_fields_allowed(self, native_models):
        """extra='allow' should accept unknown fields."""
        data = {
            "a_galaxy_workflow": "true",
            "format-version": "0.1",
            "name": "Test",
            "unknown_field": "should be kept",
        }
        wf = native_models.NativeGalaxyWorkflow.model_validate(data)
        assert wf.name == "Test"
