"""EffectSchemaCodeGen — generates Effect Schema TypeScript from schema-salad."""

from __future__ import annotations

import ast
import re
from collections.abc import MutableSequence
from io import StringIO
from typing import IO, Final

from schema_salad.codegen_base import TypeDef
from schema_salad.schema import shortname

from .codegen_base import CodeGenBase, split_top_level

_PRIM_EFFECT: Final[dict[str, str]] = {
    "http://www.w3.org/2001/XMLSchema#string": "Schema.String",
    "http://www.w3.org/2001/XMLSchema#int": "Schema.Number",
    "http://www.w3.org/2001/XMLSchema#long": "Schema.Number",
    "http://www.w3.org/2001/XMLSchema#float": "Schema.Number",
    "http://www.w3.org/2001/XMLSchema#double": "Schema.Number",
    "http://www.w3.org/2001/XMLSchema#boolean": "Schema.Boolean",
    "https://w3id.org/cwl/salad#null": "Schema.Null",
    "https://w3id.org/cwl/salad#Any": "Schema.Unknown",
    "string": "Schema.String",
    "int": "Schema.Number",
    "long": "Schema.Number",
    "float": "Schema.Number",
    "double": "Schema.Number",
    "boolean": "Schema.Boolean",
    "null": "Schema.Null",
    "Any": "Schema.Unknown",
}

_PRIM_TYPEDEFS: Final[dict[str, TypeDef]] = {
    k: TypeDef(name=v, init=v, instance_type=v) for k, v in _PRIM_EFFECT.items()
}

_PY_TO_EFFECT_PRIMS: Final[dict[str, str]] = {
    "str": "Schema.String",
    "int": "Schema.Number",
    "float": "Schema.Number",
    "bool": "Schema.Boolean",
    "None": "Schema.Null",
    "Any": "Schema.Unknown",
}

_SCHEMA_REF_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+Schema)\b")


def _python_type_to_effect(py_type: str) -> str:
    """Convert a Python type expression to Effect Schema.

    Handles: dict[K, V] -> Schema.Record({key: K, value: V}),
    list[T] -> Schema.Array(T), primitive names, and | unions.
    """
    py_type = py_type.strip()

    # Union with | — split at top level first
    top_parts = split_top_level(py_type, "|")
    if len(top_parts) > 1:
        converted = [_python_type_to_effect(p) for p in top_parts]
        return f"Schema.Union({', '.join(converted)})"

    # dict[K, V] -> Schema.Record({ key: K, value: V })
    dict_match = re.match(r"^dict\[(.+)\]$", py_type)
    if dict_match:
        inner = dict_match.group(1)
        parts = split_top_level(inner, ",")
        if len(parts) == 2:
            k = _python_type_to_effect(parts[0])
            v = _python_type_to_effect(parts[1])
            return f"Schema.Record({{ key: {k}, value: {v} }})"

    # list[T] -> Schema.Array(T)
    list_match = re.match(r"^list\[(.+)\]$", py_type)
    if list_match:
        return f"Schema.Array({_python_type_to_effect(list_match.group(1))})"

    # Literal["value"] -> Schema.Literal("value")
    literal_match = re.match(r"""^Literal\[["'](.+)["']\]$""", py_type)
    if literal_match:
        return f'Schema.Literal("{literal_match.group(1)}")'

    # Primitive mapping
    if py_type in _PY_TO_EFFECT_PRIMS:
        return _PY_TO_EFFECT_PRIMS[py_type]

    # Class name — assume schema reference
    return f"{py_type}Schema"


def _extract_schema_refs(code: str) -> set[str]:
    """Extract FooSchema references from generated code, stripping the Schema suffix."""
    return {m.group(1)[: -len("Schema")] for m in _SCHEMA_REF_RE.finditer(code)}


def _wrap_forward_refs(code: str, forward_refs: set[str]) -> str:
    """Wrap forward-referenced schemas with Schema.suspend(() => ...).

    Avoids wrapping in declaration, typeof, or spread contexts.
    """
    for ref in forward_refs:
        schema_name = f"{ref}Schema"
        pattern = rf"(?<!const )(?<!typeof )(?<!\.\.\.)(\b{re.escape(schema_name)}\b)(?!\.Type)(?!\.fields)"
        code = re.sub(
            pattern,
            rf'Schema.suspend((): Schema.Schema<any> => {schema_name}).annotations({{ identifier: "{schema_name}" }})',
            code,
        )
    return code


class EffectSchemaCodeGen(CodeGenBase):
    """Generate Effect Schema TypeScript from schema-salad definitions."""

    def __init__(
        self,
        out: IO[str],
        copyright: str | None = None,
        parser_info: str = "",
        salad_version: str = "v1.1",
    ) -> None:
        super().__init__(out, copyright=copyright, parser_info=parser_info, salad_version=salad_version)
        self._enum_code: StringIO = StringIO()
        self._discriminators: list[tuple[str, str, dict[str, str]]] = []

        # Per-class buffering for topological sort
        self._struct_defs: list[tuple[str, str]] = []  # (class_name, code)
        self._current_struct_buf: StringIO = StringIO()

    # ── backend-specific type helpers ──

    def _primitive_typedefs(self) -> dict[str, TypeDef]:
        return _PRIM_TYPEDEFS

    def _array_type_str(self, inner: str) -> str:
        return f"Schema.Array({inner})"

    def _union_type_str(self, parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return f"Schema.Union({', '.join(parts)})"

    def _type_ref_str(self, safe_name: str) -> str:
        return f"{safe_name}Schema"

    def _single_symbol_type_str(self, symbol_value: str) -> str:
        return f'Schema.Literal("{symbol_value}")'

    def _emit_enum(self, safe: str, symbols: list[str], doc: str) -> None:
        if doc:
            doc_clean = doc.strip().replace("*/", "* /")
            self._enum_code.write(f"/**\n * {doc_clean}\n */\n")
        sym_literals = [f'"{sym}"' for sym in symbols]
        self._enum_code.write(f"export const {safe}Schema = Schema.Literal({', '.join(sym_literals)})\n")
        self._enum_code.write(f"export type {safe} = typeof {safe}Schema.Type\n\n")

    # ── output methods ──

    def prologue(self) -> None:
        self.out.write("// Auto-generated by schema-salad-plus-pydantic — do not edit.\n")
        if self.copyright:
            self.out.write(f"// Original schema is {self.copyright}.\n")
        self.out.write('\nimport { Schema } from "effect"\n\n')

        for td in _PRIM_TYPEDEFS.values():
            self.declare_type(td)

    def begin_class(
        self,
        classname: str,
        extends: MutableSequence[str],
        doc: str,
        abstract: bool,
        field_names: MutableSequence[str],
        idfield: str,
        optional_fields: set[str],
    ) -> None:
        safe = self.safe_name(classname)
        self._current_class = safe
        self._current_extends = [self.safe_name(e) for e in extends]
        self._classes.append(safe)
        self._current_class_inherited_from = {}

        self._current_struct_buf = StringIO()

        if doc:
            doc_clean = doc.strip().replace("*/", "* /")
            self._current_struct_buf.write(f"/**\n * {doc_clean}\n */\n")

        self._current_struct_buf.write(f"export const {safe}Schema = Schema.Struct({{\n")

        for parent in self._current_extends:
            self._current_struct_buf.write(f"  ...{parent}Schema.fields,\n")

    def end_class(self, classname: str, field_names: list[str]) -> None:
        self._current_struct_buf.write("})\n")
        self._current_struct_buf.write(
            f"export type {self._current_class} = typeof {self._current_class}Schema.Type\n\n"
        )
        self._struct_defs.append((self._current_class, self._current_struct_buf.getvalue()))
        self._current_class = ""
        self._current_extends = []
        self._current_class_inherited_from = {}

    def declare_field(
        self,
        name: str,
        fieldtype: TypeDef,
        doc: str | None,
        optional: bool,
        subscope: str | None,
    ) -> None:
        inherited_from = self._current_class_inherited_from.get(shortname(name))
        if inherited_from and inherited_from in self._current_extends:
            self._clear_field_annotations()
            return

        json_key = shortname(name)

        if self._field_pydantic_alias:
            prop_name = self._field_pydantic_alias
        else:
            prop_name = json_key

        if self._field_pydantic_type:
            type_ann = _python_type_to_effect(self._field_pydantic_type)
            if optional and "Schema.Null" not in type_ann:
                type_ann = f"Schema.Union({type_ann}, Schema.Null)"
        else:
            type_ann = fieldtype.instance_type or fieldtype.name
            if optional and "Schema.Null" not in type_ann:
                type_ann = f"Schema.Union({type_ann}, Schema.Null)"

        if optional:
            type_ann = f"Schema.optional({type_ann})"

        if self._field_pydantic_discriminator_field and self._field_pydantic_discriminator_map:
            disc_map = ast.literal_eval(self._field_pydantic_discriminator_map)
            union_parts = list(disc_map.values())
            union_type = " | ".join(union_parts)
            self._discriminators.append((self._field_pydantic_discriminator_field, union_type, disc_map))

        needs_quote = not prop_name.isidentifier() or "-" in prop_name
        prop_str = f'"{prop_name}"' if needs_quote else prop_name

        if doc:
            doc_escaped = doc.strip().replace("*/", "* /").replace("\n", " ")
            if len(doc_escaped) > 200:
                doc_escaped = doc_escaped[:197] + "..."
            self._current_struct_buf.write(f"  /** {doc_escaped} */\n")

        self._current_struct_buf.write(f"  {prop_str}: {type_ann},\n")
        self._clear_field_annotations()

    def declare_id_field(
        self,
        name: str,
        fieldtype: TypeDef,
        doc: str | None,
        optional: bool,
    ) -> None:
        self.declare_field(name, fieldtype, doc, optional, None)

    def _topo_sort_structs(self) -> list[tuple[str, str]]:
        """Sort struct definitions so dependencies come before dependents.

        For cyclic dependencies, wraps forward references with Schema.suspend().
        """
        by_name: dict[str, str] = {name: code for name, code in self._struct_defs}
        struct_names = set(by_name.keys())

        # Extract deps for each struct (only deps that are other structs)
        deps: dict[str, set[str]] = {}
        for name, code in self._struct_defs:
            refs = _extract_schema_refs(code)
            refs.discard(name)
            deps[name] = refs & struct_names

        result_names: list[str] = []
        visited: set[str] = set()
        in_stack: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in in_stack:
                return  # cycle — break it
            in_stack.add(name)
            for dep in deps.get(name, set()):
                visit(dep)
            in_stack.discard(name)
            visited.add(name)
            result_names.append(name)

        for name, _ in self._struct_defs:
            visit(name)

        # Wrap forward/self references with Schema.suspend for schemas that
        # reference themselves or appear before their dependency is defined
        emitted: set[str] = set()
        result: list[tuple[str, str]] = []
        for name in result_names:
            code = by_name[name]
            refs = _extract_schema_refs(code)
            # Self-references need suspend too (don't discard name)
            forward_refs = (refs & struct_names) - emitted
            if forward_refs:
                code = _wrap_forward_refs(code, forward_refs)
            result.append((name, code))
            emitted.add(name)

        return result

    def epilogue(self, root_loader: TypeDef) -> None:
        self.out.write(self._enum_code.getvalue())

        for _name, code in self._topo_sort_structs():
            self.out.write(code)

        for disc_field, union_type, disc_map in self._discriminators:
            for disc_value, type_name in disc_map.items():
                func_name = f"is{type_name}"
                self.out.write(f"export function {func_name}(v: {union_type}): v is {type_name} {{\n")
                self.out.write(f'  return v?.{disc_field} === "{disc_value}";\n')
                self.out.write("}\n\n")
