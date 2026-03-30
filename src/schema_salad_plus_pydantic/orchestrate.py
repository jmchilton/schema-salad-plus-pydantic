"""Minimal orchestrator for pydantic code generation from schema-salad schemas.

Reimplements the core of schema_salad.codegen.codegen() with pydantic-specific
handling and support for pydantic:* field annotations.
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping, MutableSequence
from typing import IO, Any, Final

from schema_salad import schema
from schema_salad.ref_resolver import Loader
from schema_salad.schema import shortname
from schema_salad.utils import aslist

from .codegen import PydanticCodeGen
from .codegen_base import CodeGenBase
from .codegen_effect_schema import EffectSchemaCodeGen
from .codegen_typescript import TypeScriptCodeGen

FIELD_SORT_ORDER: Final = ["class", "id", "name"]
_NULL_TYPES: Final = {"null", "https://w3id.org/cwl/salad#null"}


def _is_optional(field_type: Any) -> bool:
    """Check if a field type includes null (making it optional)."""
    if isinstance(field_type, MutableSequence):
        return any(isinstance(t, str) and t in _NULL_TYPES for t in field_type)
    return False


def generate(
    schema_items: list[dict[str, Any]],
    loader: Loader,
    out: IO[str],
    copyright: str | None = None,
    parser_info: str = "",
    strict: bool = False,
    output_format: str = "pydantic",
) -> None:
    """Generate models from pre-loaded schema items."""
    j = schema.extend_and_specialize(schema_items, loader)

    gen: CodeGenBase
    if output_format == "typescript":
        gen = TypeScriptCodeGen(out, copyright=copyright, parser_info=parser_info)
    elif output_format == "effect-schema":
        gen = EffectSchemaCodeGen(out, copyright=copyright, parser_info=parser_info)
    else:
        gen = PydanticCodeGen(out, copyright=copyright, parser_info=parser_info, strict=strict)
    gen.prologue()

    document_roots: list[str] = []

    # First pass: register types and vocab
    for rec in j:
        if rec["type"] in ("enum", "map", "record", "union"):
            jld = rec.get("jsonldPredicate")
            if isinstance(jld, MutableMapping):
                gen.type_loader(rec, jld.get("_container"), jld.get("noLinkCheck"))
            else:
                gen.type_loader(rec)
            gen.add_vocab(shortname(rec["name"]), rec["name"])

    # Second pass: enum symbol registration + record processing
    for rec in j:
        if rec["type"] == "enum":
            for symbol in rec["symbols"]:
                gen.add_vocab(shortname(symbol), symbol)

        if rec["type"] == "record":
            if rec.get("documentRoot"):
                document_roots.append(rec["name"])

            field_names: list[str] = []
            optional_fields: set[str] = set()
            for field in rec.get("fields", []):
                field_name = shortname(field["name"])
                field_names.append(field_name)
                tp = field["type"]
                if _is_optional(tp):
                    optional_fields.add(field_name)

            idfield = ""
            for field in rec.get("fields", []):
                if field.get("jsonldPredicate") == "@id":
                    idfield = field.get("name", "")

            gen.begin_class(
                rec["name"],
                aslist(rec.get("extends", [])),
                rec.get("doc", ""),
                rec.get("abstract", False),
                field_names,
                idfield,
                optional_fields,
            )
            gen.add_vocab(shortname(rec["name"]), rec["name"])

            # Sort fields: class, id, name first
            sorted_fields = sorted(
                rec.get("fields", []),
                key=lambda f: (
                    FIELD_SORT_ORDER.index(f["name"].split("/")[-1])
                    if f["name"].split("/")[-1] in FIELD_SORT_ORDER
                    else 100
                ),
            )

            # Mark inherited fields on the generator
            for field in sorted_fields:
                inherited_from = field.get("inherited_from")
                if inherited_from:
                    gen.mark_field_inherited(shortname(field["name"]), inherited_from)

            # Process @id field first
            for field in sorted_fields:
                if field.get("jsonldPredicate") == "@id":
                    optional = _is_optional(field["type"])
                    _set_pydantic_annotations(gen, field)
                    uri_loader = gen.uri_loader(gen.type_loader(field["type"]), True, False, None)
                    gen.declare_id_field(
                        field["name"],
                        uri_loader,
                        field.get("doc"),
                        optional,
                    )
                    break

            # Process remaining fields
            for field in sorted_fields:
                optional = _is_optional(field["type"])
                jld = field.get("jsonldPredicate")

                if jld == "@id":
                    continue

                _set_pydantic_annotations(gen, field)

                if isinstance(jld, MutableMapping):
                    type_loader = gen.type_loader(field["type"], jld.get("_container"), jld.get("noLinkCheck"))
                    # For pydantic, we skip all the special loader wrapping
                    # (typeDSL, secondaryFilesDSL, uri_loader, idmap_loader)
                    # but still call through so the type gets registered
                    ref_scope = jld.get("refScope")
                    if jld.get("typeDSL"):
                        type_loader = gen.typedsl_loader(type_loader, ref_scope)
                    elif jld.get("secondaryFilesDSL"):
                        type_loader = gen.secondaryfilesdsl_loader(type_loader)
                    elif jld.get("_type") == "@id":
                        type_loader = gen.uri_loader(
                            type_loader, jld.get("identity", False), False, ref_scope, jld.get("noLinkCheck")
                        )
                    elif jld.get("_type") == "@vocab":
                        type_loader = gen.uri_loader(type_loader, False, True, ref_scope, jld.get("noLinkCheck"))

                    map_subject = jld.get("mapSubject")
                    if map_subject:
                        type_loader = gen.idmap_loader(field["name"], type_loader, map_subject, jld.get("mapPredicate"))
                else:
                    type_loader = gen.type_loader(field["type"])

                gen.declare_field(field["name"], type_loader, field.get("doc"), optional, None)

            gen.end_class(rec["name"], field_names)

    # Build root type
    root_type: list[Any] = list(document_roots)
    root_type.append({"type": "array", "items": document_roots})

    gen.epilogue(gen.type_loader(root_type))


def _get_pydantic_key(field: dict[str, Any], key: str) -> Any | None:
    """Get a pydantic:* annotation from a field dict, checking both short and URI-expanded forms."""
    # Short form (if schema doesn't expand)
    val = field.get(f"pydantic:{key}")
    if val is not None:
        return val
    # URI-expanded form — any namespace URI ending with the key
    for k, v in field.items():
        if k.endswith(f"#{key}") and "pydantic" in k:
            return v
    return None


def _set_pydantic_annotations(gen: CodeGenBase, field: dict[str, Any]) -> None:
    """Extract pydantic:* annotations from a field dict and set them on the generator."""
    gen.set_field_annotations(
        pydantic_type=_get_pydantic_key(field, "type"),
        pydantic_alias=_get_pydantic_key(field, "alias"),
        discriminator_field=_get_pydantic_key(field, "discriminator_field"),
        discriminator_map=_get_pydantic_key(field, "discriminator_map"),
    )


def generate_from_schema(
    schema_path: str,
    out: IO[str],
    copyright: str | None = None,
    parser_info: str = "",
    strict: bool = False,
    output_format: str = "pydantic",
) -> None:
    """Load a schema-salad schema file and generate models.

    Uses the metaschema loader directly (like schema-salad-tool --codegen)
    instead of load_schema(), which runs Avro validation that rejects
    valid schemas with [null, string, Any] unions.
    """
    from typing import cast
    from urllib.parse import urlparse

    from schema_salad.ref_resolver import file_uri
    from schema_salad.schema import get_metaschema

    schema_uri = schema_path
    if not (urlparse(schema_uri)[0] and urlparse(schema_uri)[0] in ["http", "https", "file"]):
        schema_uri = file_uri(os.path.abspath(schema_uri))

    metaschema_names, metaschema_doc, metaschema_loader = get_metaschema()
    schema_raw_doc = metaschema_loader.fetch(schema_uri)
    schema_doc, schema_metadata = metaschema_loader.resolve_all(schema_raw_doc, schema_uri)

    # Build a document loader with the schema's context
    from schema_salad.ref_resolver import Loader

    schema_ctx = schema_metadata.get("@context", {})
    salad_version = schema_metadata.get("saladVersion", "v1.1")
    document_loader = Loader(schema_ctx, salad_version=salad_version)

    generate(
        cast(list[dict[str, Any]], schema_doc),
        document_loader,
        out,
        copyright=copyright,
        parser_info=parser_info,
        strict=strict,
        output_format=output_format,
    )
