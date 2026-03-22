"""Post-process schema-salad-doc HTML to replace Any types with pydantic annotations."""

from __future__ import annotations

import re
from typing import Any

import yaml


def _extract_pydantic_annotations(
    schema_path: str,
) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Extract pydantic annotations and documentRoot info from schema.

    Returns (type_map, alias_map, document_roots) where:
      type_map: field_name -> pydantic type string
      alias_map: schema_field_name -> json_field_name (alias)
      document_roots: set of record names that have documentRoot: true
    """
    with open(schema_path) as f:
        schema = yaml.safe_load(f)

    type_map: dict[str, str] = {}
    alias_map: dict[str, str] = {}
    document_roots: set[str] = set()

    def _process_items(items: list[dict[str, Any]]) -> None:
        for item in items:
            if isinstance(item, str) or item.get("type") == "documentation":
                continue
            if item.get("type") == "record":
                if item.get("documentRoot"):
                    document_roots.add(item["name"])
                for field in item.get("fields", []):
                    field_name = field["name"].rsplit("/", 1)[-1]
                    pydantic_type = field.get("pydantic:type")
                    if pydantic_type:
                        type_map[field_name] = pydantic_type
                    pydantic_alias = field.get("pydantic:alias")
                    if pydantic_alias:
                        alias_map[field_name] = pydantic_alias

    _process_items(schema.get("$graph", []))
    return type_map, alias_map, document_roots


def _type_to_html(type_str: str) -> str:
    """Convert a pydantic type string to HTML with links to schema types.

    Wraps known type names (capitalized, not built-in) with anchor links.
    Keeps built-in types (str, int, float, bool, None, Any, dict, list) as plain text.
    """
    builtins = {"str", "int", "float", "bool", "None", "Any", "dict", "list"}

    def link_type(match: re.Match[str]) -> str:
        name = match.group(0)
        if name in builtins:
            return name
        return f'<a href="#{name}">{name}</a>'

    return str(re.sub(r"\b[A-Za-z]\w+", link_type, type_str))


def enhance_html(
    html: str,
    type_map: dict[str, str],
    alias_map: dict[str, str],
    document_roots: set[str] | None = None,
) -> str:
    """Replace Any type cells, aliased field names, and remove artificial class rows."""
    document_roots = document_roots or set()

    # Remove artificial class rows added by documentRoot: true.
    # These rows appear in document root record sections and have a class enum type.
    # Creator class fields (Person/Organization discriminators) are legitimate and
    # appear in non-documentRoot records, so they are preserved.
    if document_roots:
        for root_name in document_roots:
            # Match the class row within the section for this document root
            html = re.sub(
                r'<div class="row responsive-table-row">\s*\n'
                r"<div[^>]*><code>class</code></div>\n"
                r".*?</div>\n</div>\n",
                "",
                html,
                count=1,
                flags=re.DOTALL,
            )

    def replace_in_row(match: re.Match[str]) -> str:
        row_html = match.group(0)
        code_match = re.search(r"<code>(\w+)</code>", row_html)
        if not code_match:
            return row_html
        field_name = code_match.group(1)

        # Replace field name with alias if present
        if field_name in alias_map:
            alias = alias_map[field_name]
            row_html = row_html.replace(
                f"<code>{field_name}</code>",
                f"<code>{alias}</code>",
                1,
            )

        # Replace Any type with pydantic type
        if field_name in type_map:
            pydantic_type = type_map[field_name]
            type_html = _type_to_html(pydantic_type)
            row_html = str(
                re.sub(
                    r'<a href="#Any">Any</a>',
                    f"<code>{type_html}</code>",
                    row_html,
                )
            )

        return row_html

    return str(
        re.sub(
            r'<div class="row responsive-table-row">.*?</div>\s*</div>',
            replace_in_row,
            html,
            flags=re.DOTALL,
        )
    )


def enhance_docs(schema_path: str, html_path: str, output_path: str | None = None) -> str:
    """Load schema and HTML, enhance types/aliases/class rows, write/return result."""
    type_map, alias_map, document_roots = _extract_pydantic_annotations(schema_path)
    with open(html_path) as f:
        html = f.read()
    result = enhance_html(html, type_map, alias_map, document_roots)
    out = output_path or html_path
    with open(out, "w") as f:
        f.write(result)
    return result
