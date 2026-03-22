"""Unit tests for PydanticCodeGen output."""

from __future__ import annotations

import importlib.util
import re
import sys

import pytest
from pydantic import ValidationError


def test_generates_valid_python(generate_code_from_schema, simple_schema_path):
    """Generated code should compile without errors."""
    code = generate_code_from_schema(simple_schema_path)
    compile(code, "<generated>", "exec")


def test_expected_classes_present(generate_code_from_schema, simple_schema_path):
    """All schema records should produce classes."""
    code = generate_code_from_schema(simple_schema_path)
    for cls in ["BaseRecord", "ChildRecord", "PersonMember", "OrgMember", "BaseMember"]:
        assert f"class {cls}" in code, f"Missing class {cls}"


def test_enum_generated(generate_code_from_schema, simple_schema_path):
    """Multi-symbol enums should produce Enum classes."""
    code = generate_code_from_schema(simple_schema_path)
    assert "class StatusEnum(str, Enum):" in code
    assert 'active = "active"' in code
    assert 'inactive = "inactive"' in code
    assert 'pending = "pending"' in code


def test_single_symbol_enum_is_literal(generate_code_from_schema, simple_schema_path):
    """Single-symbol enums should use Literal type."""
    code = generate_code_from_schema(simple_schema_path)
    # PersonType has single symbol "Person" -> should be Literal["Person"]
    assert 'Literal["Person"]' in code


def test_pydantic_type_override(generate_code_from_schema, simple_schema_path):
    """Fields with pydantic:type should use the override type annotation."""
    code = generate_code_from_schema(simple_schema_path)
    assert "dict[str, str]" in code


def test_field_alias(generate_code_from_schema, simple_schema_path):
    """Hyphenated field names should get Field(alias=...)."""
    code = generate_code_from_schema(simple_schema_path)
    assert 'alias="format-version"' in code


def test_inherited_fields_not_redeclared(generate_code_from_schema, simple_schema_path):
    """Child classes should NOT redeclare fields inherited from parents."""
    code = generate_code_from_schema(simple_schema_path)

    # Find the ChildRecord class body
    child_match = re.search(r"class ChildRecord\(.*?\):\n(.*?)(?=\nclass |\n# Rebuild|\Z)", code, re.DOTALL)
    assert child_match, "ChildRecord class not found"
    child_body = child_match.group(1)

    # ChildRecord extends BaseRecord which has 'id' and 'name' fields
    # These should NOT appear in ChildRecord's body (they're inherited)
    lines = child_body.strip().split("\n")
    field_lines = [
        line.strip()
        for line in lines
        if ": " in line and not line.strip().startswith("#") and not line.strip().startswith("model_config")
    ]

    field_names = []
    for line in field_lines:
        if line and not line.startswith('"""'):
            name = line.split(":")[0].strip()
            if name:
                field_names.append(name)

    # 'id' and 'name' are inherited from BaseRecord and should not be in ChildRecord
    assert "id" not in field_names, "Inherited field 'id' should not be redeclared"
    assert "name" not in field_names, "Inherited field 'name' should not be redeclared"


def test_abstract_classes_have_fields(generate_code_from_schema, simple_schema_path):
    """Abstract base classes should declare their fields (not just 'pass')."""
    code = generate_code_from_schema(simple_schema_path)

    base_match = re.search(r"class BaseRecord\(.*?\):\n(.*?)(?=\nclass |\Z)", code, re.DOTALL)
    assert base_match, "BaseRecord class not found"
    base_body = base_match.group(1)
    # Should have field declarations, not just 'pass'
    assert "pass" not in base_body or ":" in base_body


def test_model_rebuild_calls(generate_code_from_schema, simple_schema_path):
    """All classes should have model_rebuild() calls in the epilogue."""
    code = generate_code_from_schema(simple_schema_path)
    for cls in ["BaseRecord", "ChildRecord", "PersonMember", "OrgMember"]:
        assert f"{cls}.model_rebuild()" in code, f"Missing model_rebuild for {cls}"


def test_model_config(generate_code_from_schema, simple_schema_path):
    """Classes should have model_config with populate_by_name and extra=allow."""
    code = generate_code_from_schema(simple_schema_path)
    assert "populate_by_name=True" in code
    assert 'extra="allow"' in code


def test_model_config_strict(generate_code_from_schema, simple_schema_path):
    """With strict=True, classes should use extra=forbid."""
    code = generate_code_from_schema(simple_schema_path, strict=True)
    assert "populate_by_name=True" in code
    assert 'extra="forbid"' in code
    assert 'extra="allow"' not in code


def test_strict_rejects_unknown_fields(generate_code_from_schema, simple_schema_path):
    """Strict models should raise ValidationError on unknown keys."""
    code = generate_code_from_schema(simple_schema_path, strict=True)
    spec = importlib.util.spec_from_loader("strict_models", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(code, "<strict_models>", "exec"), mod.__dict__)
    sys.modules["strict_models"] = mod

    data = {
        "name": "x",
        "status": "active",
        "format-version": "1.0",
        "items": {},
        "not_in_schema": True,
    }
    with pytest.raises(ValidationError):
        mod.ChildRecord.model_validate(data)


def test_optional_fields(generate_code_from_schema, simple_schema_path):
    """Optional fields should have None defaults."""
    code = generate_code_from_schema(simple_schema_path)
    # tags field is nullable (null | array) so should be optional
    assert "tags:" in code
    assert "None" in code


def test_load_document_function(generate_code_from_schema, simple_schema_path):
    """Should generate a load_document convenience function."""
    code = generate_code_from_schema(simple_schema_path)
    assert "def load_document(" in code


def test_parser_info(generate_code_from_schema, simple_schema_path):
    """Should generate parser_info function."""
    code = generate_code_from_schema(simple_schema_path)
    assert "def parser_info()" in code
