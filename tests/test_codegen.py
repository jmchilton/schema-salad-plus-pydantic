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


def test_discriminator_uses_python_safe_attr(generate_code_from_schema, simple_schema_path):
    """Discriminator functions should use Python-safe attr names (class_ not class) for getattr."""
    code = generate_code_from_schema(simple_schema_path)
    # The discriminator for 'class' field should use 'class_' for model instance access
    assert 'getattr(v, "class_"' in code
    # But dict access should still use the JSON key 'class'
    assert 'v.get("class"' in code


def test_discriminated_union_with_model_instances(generate_code_from_schema, simple_schema_path):
    """Discriminated unions should work with both dicts and model instances."""
    code = generate_code_from_schema(simple_schema_path)
    spec = importlib.util.spec_from_loader("disc_models", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(code, "<disc_models>", "exec"), mod.__dict__)
    sys.modules["disc_models"] = mod

    # Dict input — discriminator reads v.get("class")
    data = {"members": [{"class": "Organization", "name": "Org1", "url": "https://example.com"}]}
    record = mod.ChildRecord.model_validate(data)
    assert len(record.members) == 1
    assert isinstance(record.members[0], mod.OrgMember)
    assert record.members[0].name == "Org1"

    # Model instance round-trip — discriminator reads getattr(v, "class_")
    org = mod.OrgMember(name="Org2", url="https://example.com")
    data2 = {"members": [org]}
    record2 = mod.ChildRecord.model_validate(data2)
    assert isinstance(record2.members[0], mod.OrgMember)
    assert record2.members[0].name == "Org2"

    # Person variant
    person = mod.PersonMember(name="Alice", email="alice@example.com")
    data3 = {"members": [person, org]}
    record3 = mod.ChildRecord.model_validate(data3)
    assert isinstance(record3.members[0], mod.PersonMember)
    assert isinstance(record3.members[1], mod.OrgMember)


def test_multi_value_discriminator_map(generate_code_from_schema, simple_schema_path):
    """Multi-value discriminator map should produce correct disc function with all entries."""
    code = generate_code_from_schema(simple_schema_path)
    assert '"circle": "Circle"' in code
    assert '"box": "Box"' in code
    assert '"rectangle": "Box"' in code


def test_discriminator_default(generate_code_from_schema, simple_schema_path):
    """Discriminator with default should use default fallback instead of disc_val."""
    code = generate_code_from_schema(simple_schema_path)
    # _discriminate_shapes should use "Box" as default
    assert 'disc_map.get(disc_val, "Box")' in code
    # _discriminate_members should NOT have a default (uses disc_val fallback)
    assert "disc_map.get(disc_val, disc_val)" in code


def test_complex_type_with_discriminator(generate_code_from_schema, simple_schema_path):
    """list[A|B] | dict[str, A|B] should apply discriminator only to list branch."""
    code = generate_code_from_schema(simple_schema_path)
    # Canvas.shapes should have Discriminator in list branch but not dict branch
    assert "list[Annotated[" in code
    assert "Discriminator(_discriminate_shapes)" in code
    # dict branch should pass through without Discriminator/Tag wrapping
    assert "dict[str, Circle | Box]" in code


def test_discriminator_default_runtime(generate_code_from_schema, simple_schema_path):
    """Discriminator default should resolve unknown kind values to the default type."""
    code = generate_code_from_schema(simple_schema_path)
    spec = importlib.util.spec_from_loader("canvas_models", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(code, "<canvas_models>", "exec"), mod.__dict__)
    sys.modules["canvas_models"] = mod

    # circle -> Circle
    data = {"shapes": [{"kind": "circle", "radius": 5.0}]}
    canvas = mod.Canvas.model_validate(data)
    assert isinstance(canvas.shapes[0], mod.Circle)
    assert canvas.shapes[0].radius == 5.0

    # rectangle -> Box (multi-value map)
    data2 = {"shapes": [{"kind": "rectangle", "width": 10.0}]}
    canvas2 = mod.Canvas.model_validate(data2)
    assert isinstance(canvas2.shapes[0], mod.Box)

    # box -> Box
    data3 = {"shapes": [{"kind": "box", "width": 3.0}]}
    canvas3 = mod.Canvas.model_validate(data3)
    assert isinstance(canvas3.shapes[0], mod.Box)

    # Mixed list
    data4 = {"shapes": [{"kind": "circle", "radius": 1.0}, {"kind": "rectangle", "width": 2.0}]}
    canvas4 = mod.Canvas.model_validate(data4)
    assert isinstance(canvas4.shapes[0], mod.Circle)
    assert isinstance(canvas4.shapes[1], mod.Box)
