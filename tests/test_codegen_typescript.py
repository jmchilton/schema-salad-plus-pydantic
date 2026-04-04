"""Unit tests for TypeScript code generation output."""

from __future__ import annotations

import re

import pytest

from schema_salad_plus_pydantic.codegen_typescript import _python_type_to_ts


class TestPythonTypeToTs:
    """Unit tests for the Python->TypeScript type translation helper."""

    @pytest.mark.parametrize(
        "py_type,expected",
        [
            ("str", "string"),
            ("int", "number"),
            ("float", "number"),
            ("bool", "boolean"),
            ("None", "null"),
            ("Any", "unknown"),
            ("MyClass", "MyClass"),
            ("dict[str, str]", "Record<string, string>"),
            ("list[int]", "Array<number>"),
            ('Literal["foo"]', '"foo"'),
            ("Literal['bar']", '"bar"'),
            ("str | None", "string | null"),
            # nested generics with top-level union
            ("list[A | B] | None", "Array<A | B> | null"),
            ("dict[str, A | B] | None", "Record<string, A | B> | null"),
            # complex nested
            ("list[WorkflowStep] | dict[str, WorkflowStep]", "Array<WorkflowStep> | Record<string, WorkflowStep>"),
        ],
    )
    def test_type_conversion(self, py_type: str, expected: str) -> None:
        assert _python_type_to_ts(py_type) == expected


def test_generates_valid_typescript(generate_typescript_from_schema, simple_schema_path):
    """Generated code should look like valid TypeScript (interfaces, no Python syntax)."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert "export interface" in code
    assert "BaseModel" not in code
    assert "from pydantic" not in code


def test_header_comment(generate_typescript_from_schema, simple_schema_path):
    """Generated code should have a header comment."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert "Auto-generated" in code
    assert "do not edit" in code


def test_expected_interfaces_present(generate_typescript_from_schema, simple_schema_path):
    """All schema records should produce interfaces."""
    code = generate_typescript_from_schema(simple_schema_path)
    for name in ["BaseRecord", "ChildRecord", "PersonMember", "OrgMember", "BaseMember"]:
        assert f"export interface {name}" in code, f"Missing interface {name}"


def test_enum_generated(generate_typescript_from_schema, simple_schema_path):
    """Multi-symbol enums should produce string union types."""
    code = generate_typescript_from_schema(simple_schema_path)
    # Should have a type alias for StatusEnum as a string union
    assert "type StatusEnum" in code
    assert '"active"' in code
    assert '"inactive"' in code
    assert '"pending"' in code


def test_single_symbol_is_literal_type(generate_typescript_from_schema, simple_schema_path):
    """Single-symbol enums should produce a string literal type."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert '"Person"' in code


def test_primitive_type_mapping(generate_typescript_from_schema, simple_schema_path):
    """Primitive types should map to TypeScript equivalents."""
    code = generate_typescript_from_schema(simple_schema_path)
    # string fields should use TS 'string' not Python 'str'
    assert "string" in code
    assert re.search(r":\s*str[^i]", code) is None, "Should not contain Python 'str' type"


def test_optional_fields(generate_typescript_from_schema, simple_schema_path):
    """Optional fields should use ?: syntax."""
    code = generate_typescript_from_schema(simple_schema_path)
    # tags is nullable -> should be optional
    assert "tags?" in code


def test_inheritance(generate_typescript_from_schema, simple_schema_path):
    """Child interfaces should extend parent interfaces."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert "export interface ChildRecord extends BaseRecord" in code


def test_inherited_fields_not_redeclared(generate_typescript_from_schema, simple_schema_path):
    """Child interfaces should NOT redeclare fields inherited from parents."""
    code = generate_typescript_from_schema(simple_schema_path)
    # Find ChildRecord interface body
    child_match = re.search(r"export interface ChildRecord[^{]*\{(.*?)\}", code, re.DOTALL)
    assert child_match, "ChildRecord interface not found"
    child_body = child_match.group(1)
    # 'id' and 'name' are inherited from BaseRecord
    field_lines = [line.strip() for line in child_body.split("\n") if ":" in line and not line.strip().startswith("//")]
    field_names = [line.split(":")[0].strip().rstrip("?") for line in field_lines]
    assert "id" not in field_names, "Inherited field 'id' should not be redeclared"
    assert "name" not in field_names, "Inherited field 'name' should not be redeclared"


def test_type_override(generate_typescript_from_schema, simple_schema_path):
    """pydantic:type dict[str, str] should become Record<string, string>."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert "Record<string, string>" in code


def test_field_alias(generate_typescript_from_schema, simple_schema_path):
    """Hyphenated field names should use the alias as property name (quoted)."""
    code = generate_typescript_from_schema(simple_schema_path)
    # format-version has pydantic:alias "format-version"
    assert '"format-version"' in code


def test_discriminated_union_type_guard(generate_typescript_from_schema, simple_schema_path):
    """Discriminated unions should produce type guard functions with proper union parameter."""
    code = generate_typescript_from_schema(simple_schema_path)
    assert "function isPersonMember" in code
    assert "function isOrgMember" in code
    # Type guard should use the union type, not 'any'
    assert "v: PersonMember | OrgMember" in code
    assert "v: any" not in code


def test_array_type(generate_typescript_from_schema, simple_schema_path):
    """Array types should use Array<T> or T[] syntax."""
    code = generate_typescript_from_schema(simple_schema_path)
    # tags is an array of strings
    assert "Array<string>" in code or "string[]" in code


def test_multi_value_type_guard_dedup(generate_typescript_from_schema, simple_schema_path):
    """Multi-value discriminator maps should produce one guard per type with OR conditions."""
    code = generate_typescript_from_schema(simple_schema_path)
    # Should have exactly one isBox guard, not two
    assert code.count("function isBox") == 1
    assert code.count("function isCircle") == 1
    # isBox should check both values
    assert 'v?.kind === "box" || v?.kind === "rectangle"' in code
    # Union type should not repeat Box
    assert "Circle | Box" in code
    # Should not have "Circle | Box | Box"
    assert "Box | Box" not in code


def test_cli_format_typescript(simple_schema_path):
    """CLI --format=typescript should produce TypeScript output."""
    import sys
    from io import StringIO

    from schema_salad_plus_pydantic.cli import main

    old_stdout = sys.stdout
    sys.stdout = buf = StringIO()
    try:
        main(["generate", str(simple_schema_path), "--format", "typescript"])
    finally:
        sys.stdout = old_stdout
    code = buf.getvalue()
    assert "export interface" in code
