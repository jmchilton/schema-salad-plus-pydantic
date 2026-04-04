"""Shared base for code generation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import MutableSequence
from typing import IO, Any, Final

from schema_salad import schema
from schema_salad.codegen_base import LazyInitDef, TypeDef
from schema_salad.schema import shortname


def split_top_level(s: str, sep: str) -> list[str]:
    """Split a string on *sep* only at the top level (not inside brackets)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in ("[", "<", "("):
            depth += 1
            current.append(c)
        elif c in ("]", ">", ")"):
            depth -= 1
            current.append(c)
        elif depth == 0 and s[i : i + len(sep)] == sep:
            parts.append("".join(current))
            current = []
            i += len(sep)
            continue
        else:
            current.append(c)
        i += 1
    parts.append("".join(current))
    return parts


class CodeGenBase(ABC):
    """Base class for schema-salad code generation backends.

    Holds shared state (collected types, vocab, field annotations, inherited
    field tracking) and the type_loader logic.  Subclasses implement the
    output-specific methods (prologue, begin_class, declare_field, etc.) and
    override _array_type / _primitive_typedefs to control type representations.
    """

    def __init__(
        self,
        out: IO[str],
        copyright: str | None = None,
        parser_info: str = "",
        salad_version: str = "v1.1",
    ) -> None:
        self.collected_types: OrderedDict[str, TypeDef] = OrderedDict()
        self.lazy_inits: OrderedDict[str, LazyInitDef] = OrderedDict()
        self.vocab: dict[str, str] = {}

        self.out: Final = out
        self.copyright = copyright
        self.parser_info = parser_info
        self.salad_version = salad_version

        self._current_class: str = ""
        self._current_extends: list[str] = []
        self._classes: list[str] = []
        self._enums_emitted: set[str] = set()

        # Per-field annotation overrides (set by orchestrator before declare_field)
        self._field_pydantic_type: str | None = None
        self._field_pydantic_alias: str | None = None
        self._field_pydantic_discriminator_field: str | None = None
        self._field_pydantic_discriminator_map: str | None = None
        self._field_pydantic_discriminator_default: str | None = None

        # Track inherited fields per class
        self._current_class_inherited_from: dict[str, str] = {}

    # ── shared helpers ──

    def declare_type(self, declared_type: TypeDef) -> TypeDef:
        if declared_type not in self.collected_types.values():
            self.collected_types[declared_type.name] = declared_type
        return declared_type

    def add_lazy_init(self, lazy_init: LazyInitDef) -> None:
        self.lazy_inits[lazy_init.name] = lazy_init

    def add_vocab(self, name: str, uri: str) -> None:
        self.vocab[name] = uri

    @staticmethod
    def safe_name(name: str) -> str:
        avn = schema.avro_field_name(name)
        if avn.startswith("anon."):
            avn = avn[5:]
        elif avn and avn[0].isdigit():
            avn = f"_{avn}"
        return avn.replace(".", "_")

    def set_field_annotations(
        self,
        pydantic_type: str | None = None,
        pydantic_alias: str | None = None,
        discriminator_field: str | None = None,
        discriminator_map: str | None = None,
        discriminator_default: str | None = None,
    ) -> None:
        self._field_pydantic_type = pydantic_type
        self._field_pydantic_alias = pydantic_alias
        self._field_pydantic_discriminator_field = discriminator_field
        self._field_pydantic_discriminator_map = discriminator_map
        self._field_pydantic_discriminator_default = discriminator_default

    def _clear_field_annotations(self) -> None:
        self._field_pydantic_type = None
        self._field_pydantic_alias = None
        self._field_pydantic_discriminator_field = None
        self._field_pydantic_discriminator_map = None
        self._field_pydantic_discriminator_default = None

    def mark_field_inherited(self, field_shortname: str, inherited_from: str) -> None:
        parent_safe = self.safe_name(inherited_from)
        self._current_class_inherited_from[field_shortname] = parent_safe

    # ── no-op loader wrappers (pydantic/TS don't need these) ──

    def uri_loader(
        self,
        inner: TypeDef,
        scoped_id: bool,
        vocab_term: bool,
        ref_scope: int | None,
        no_link_check: bool | None = None,
    ) -> TypeDef:
        return inner

    def idmap_loader(self, field: str, inner: TypeDef, map_subject: str, map_predicate: str | None) -> TypeDef:
        return inner

    def typedsl_loader(self, inner: TypeDef, ref_scope: int | None) -> TypeDef:
        return inner

    def secondaryfilesdsl_loader(self, inner: TypeDef) -> TypeDef:
        return inner

    # ── type_loader: shared type resolution ──

    @abstractmethod
    def _array_type_str(self, inner: str) -> str:
        """Return the array type string for the backend (e.g. list[T] or Array<T>)."""

    @abstractmethod
    def _primitive_typedefs(self) -> dict[str, TypeDef]:
        """Return the backend's primitive type definitions."""

    @abstractmethod
    def _emit_enum(self, safe: str, symbols: list[str], doc: str) -> None:
        """Emit a multi-symbol enum definition to the backend's buffer."""

    @abstractmethod
    def _single_symbol_type_str(self, symbol_value: str) -> str:
        """Return the type string for a single-symbol enum."""

    def _union_type_str(self, parts: list[str]) -> str:
        """Return the union type string for the backend (e.g. A | B or Schema.Union(A, B))."""
        return " | ".join(parts)

    def _type_ref_str(self, safe_name: str) -> str:
        """Return the type reference string for a named type (record/enum)."""
        return safe_name

    def type_loader(
        self,
        type_declaration: list[Any] | dict[str, Any] | str,
        container: str | None = None,
        no_link_check: bool | None = None,
    ) -> TypeDef:
        td = type_declaration
        prims = self._primitive_typedefs()

        if isinstance(td, MutableSequence):
            parts = []
            for item in td:
                sub = self.type_loader(item)
                parts.append(sub.instance_type or sub.name)
            seen: set[str] = set()
            unique_parts: list[str] = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    unique_parts.append(p)
            union_str = self._union_type_str(unique_parts)
            name = "union_of_" + "_or_".join(unique_parts)
            return self.declare_type(TypeDef(name=name, init=union_str, instance_type=union_str))

        if isinstance(td, dict):
            t = td.get("type")
            if t in ("array", "https://w3id.org/cwl/salad#array") and "items" in td:
                items = td["items"]
                if isinstance(items, list):
                    inner_parts = []
                    for it in items:
                        inner_td = self.type_loader(it)
                        inner_parts.append(inner_td.instance_type or inner_td.name)
                    inner_str = self._union_type_str(inner_parts)
                    type_str = self._array_type_str(inner_str)
                else:
                    inner = self.type_loader(items)
                    type_str = self._array_type_str(inner.instance_type or inner.name)
                return self.declare_type(TypeDef(name=f"array_{type_str}", init=type_str, instance_type=type_str))

            if t in ("enum", "https://w3id.org/cwl/salad#enum") and "symbols" in td and "name" in td:
                symbols = td["symbols"]
                name = td["name"]
                rest = {k: v for k, v in td.items() if k not in ("type", "symbols", "name")}
                safe = self.safe_name(name)
                for sym in symbols:
                    self.add_vocab(shortname(sym), sym)

                if len(symbols) == 1:
                    sym_val = shortname(symbols[0])
                    type_str = self._single_symbol_type_str(sym_val)
                    return self.declare_type(TypeDef(name=f"{safe}Loader", init=type_str, instance_type=type_str))
                if safe not in self._enums_emitted:
                    self._enums_emitted.add(safe)
                    doc = rest.get("doc", "")
                    if isinstance(doc, list):
                        doc = "\n".join(doc)
                    self._emit_enum(safe, [shortname(s) for s in symbols], str(doc))

                ref = self._type_ref_str(safe)
                return self.declare_type(TypeDef(name=f"{safe}Loader", init=ref, instance_type=ref))

            if t in ("record", "https://w3id.org/cwl/salad#record") and "name" in td:
                name = td["name"]
                rest = {k: v for k, v in td.items() if k not in ("type", "name")}
                safe = self.safe_name(name)
                ref = self._type_ref_str(safe)
                return self.declare_type(
                    TypeDef(
                        name=f"{safe}Loader",
                        init=ref,
                        instance_type=ref,
                        abstract=bool(rest.get("abstract", False)),
                    )
                )

            if (
                t in ("union", "https://w3id.org/cwl/salad#union")
                and "name" in td
                and isinstance(td.get("names"), list)
            ):
                name = td["name"]
                names = td["names"]
                safe = self.safe_name(name)
                loader_name = f"{safe}Loader"
                parts = []
                for n in names:
                    inner_td = self.type_loader(n)
                    parts.append(inner_td.instance_type or inner_td.name)
                union_str = self._union_type_str(parts)
                return self.declare_type(TypeDef(name=loader_name, init=union_str, instance_type=union_str))

        if isinstance(td, str):
            if td in prims:
                return prims[td]
            safe = self.safe_name(td)
            loader_key = f"{safe}Loader"
            if loader_key in self.collected_types:
                return self.collected_types[loader_key]
            ref = self._type_ref_str(safe)
            return self.declare_type(TypeDef(name=loader_key, init=ref, instance_type=ref))

        raise ValueError(f"Unhandled type declaration: {type_declaration}")

    # ── abstract output methods ──

    @abstractmethod
    def prologue(self) -> None: ...

    @abstractmethod
    def begin_class(
        self,
        classname: str,
        extends: MutableSequence[str],
        doc: str,
        abstract: bool,
        field_names: MutableSequence[str],
        idfield: str,
        optional_fields: set[str],
    ) -> None: ...

    @abstractmethod
    def end_class(self, classname: str, field_names: list[str]) -> None: ...

    @abstractmethod
    def declare_field(
        self,
        name: str,
        fieldtype: TypeDef,
        doc: str | None,
        optional: bool,
        subscope: str | None,
    ) -> None: ...

    @abstractmethod
    def declare_id_field(
        self,
        name: str,
        fieldtype: TypeDef,
        doc: str | None,
        optional: bool,
    ) -> None: ...

    @abstractmethod
    def epilogue(self, root_loader: TypeDef) -> None: ...
