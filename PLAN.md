# schema-salad-plus-pydantic

## Goal

Subclass `CodeGenBase` from schema-salad to generate pydantic v2 `BaseModel` classes. Read `pydantic:type` and `pydantic:discriminator*` annotations from schema fields to handle types schema-salad can't natively express (dict maps, discriminated unions with real class names, aliased fields). Reuse schema-salad's orchestration so our generator plugs into the same pipeline as `PythonCodeGen`.

## Schema Annotation Convention

```yaml
- name: steps
  type: Any?
  pydantic:type: "dict[str, NativeStep]"

- name: creator
  type: Any?
  pydantic:type: "list[NativeCreatorPerson | NativeCreatorOrganization] | None"
  pydantic:discriminator_field: "class"
  pydantic:discriminator_map: '{"Person": "NativeCreatorPerson", "Organization": "NativeCreatorOrganization"}'
```

Schema-salad preserves `:`-namespaced keys on field dicts through the entire pipeline (see "Extension Annotation Extraction" below).

## Project Structure

```
schema-salad-plus-pydantic/
├── pyproject.toml
├── src/
│   └── schema_salad_plus_pydantic/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point
│       ├── codegen.py          # PydanticCodeGen(CodeGenBase)
│       └── orchestrate.py      # Minimal reimplementation of codegen() loop
└── tests/
    ├── conftest.py
    ├── test_codegen.py         # Unit tests for generator methods
    ├── test_roundtrip.py       # Generate -> import -> validate real data
    └── schemas/
        └── simple.yml          # Minimal test schema with pydantic annotations
```

## Inheritance Strategy

Schema-salad's `extend_and_specialize()` **merges/flattens** parent fields into child records. After processing, a child record's `fields` array contains all parent fields (marked with `inherited_from`) plus its own fields. However, the original `extends` list is preserved on the record dict and passed to `begin_class()`.

Schema-salad's `PythonCodeGen` uses Python class inheritance (`class Child(Parent):`) but declares ALL fields (parent + child) in the child's `__init__`. Parents are abstract marker classes with `pass` bodies.

**Our approach: Use pydantic class inheritance properly.**

- Abstract base records -> emit as `class Base(BaseModel):` with their fields declared as pydantic fields
- Concrete child records -> emit as `class Child(Base):` with ONLY child-specific fields (filter out fields where `inherited_from` is set)
- This gives us real pydantic inheritance: parent fields inherited, child fields added
- Diamond inheritance works because `extend_and_specialize()` deduplicates by short name
- Field overrides (narrower types in child) are supported — schema-salad validates subtype compatibility via `is_subtype()`

**Implementation detail:** In `declare_field()`, check `field.get("inherited_from")`. If set and the current class extends that parent, skip the field (it's inherited). Only declare fields that are new to this class.

**Edge case — multiple inheritance:** Pydantic supports multiple inheritance for `BaseModel` subclasses. `NativeStep` extends `HasStepErrors`, `HasStepPosition`, `HasUUID`, `ReferencesTool` — this maps directly to `class NativeStep(HasStepErrors, HasStepPosition, HasUUID, ReferencesTool):`.

## Orchestrator Strategy

**Minimal reimplementation** of schema-salad's `codegen()` function (~80-100 lines), NOT vendoring the full function.

Rationale from research:
- The `codegen()` function is stable (~5 commits/year, mostly type annotation updates)
- ~60% is language-agnostic orchestration, ~40% is language-specific hooks
- No clean way to hook into `codegen()` without monkey-patching (hardcoded match statement)
- For pydantic, we can skip: URI loader wrapping, typeDSL, secondaryFilesDSL, idmap_loader — these are CWL-specific concerns that pydantic's own validation replaces

**What our orchestrator must handle:**
1. Call `extend_and_specialize()` to resolve inheritance
2. Register types/vocab in a first pass
3. Field sorting (class, id, name fields first — critical for inheritance)
4. Optional field detection (check for `null` in union type at position 0)
5. Abstract class handling (emit marker base classes)
6. Document root detection (for `load_document()` entry point)
7. Extract `pydantic:*` annotations from field dicts before calling `declare_field()`

**What we skip entirely:**
- `uri_loader()` wrapping
- `idmap_loader()` wrapping
- `typedsl_loader()` / `secondaryfilesdsl_loader()`
- `@vocab` term URI resolution

## Extension Annotation Extraction

**Confirmed: custom keys survive the full pipeline.** Research traced the path:

1. Schema YAML with `pydantic:type` on fields
2. `load_schema()` validates with `strict=True` but `strict_foreign_properties=False` — unknown keys pass through
3. `extend_and_specialize()` uses `deepcopy_strip()` which copies ALL dict keys, no filtering
4. Field dicts arrive at codegen loop with `pydantic:*` keys intact
5. When parent fields merge into children, extra keys are preserved (simple dict copy)

**No pre-pass needed.** Our orchestrator accesses `field.get("pydantic:type")` etc. directly from field dicts during the codegen loop, then stashes them on the generator instance for `declare_field()` to use.

Note: the keys will be `pydantic:type` as raw strings in the field dicts (not URL-expanded), since expansion only happens during document loading, not schema processing.

## `PydanticCodeGen(CodeGenBase)` -- Method by Method

### `__init__(self, out, copyright, parser_info, salad_version)`

Same signature as `PythonCodeGen`. Track: current class fields, collected enums, forward ref set, pydantic extension annotations per field, set of classes needing `model_rebuild()`.

### `prologue()`

Emit: `from __future__ import annotations`, pydantic imports (`BaseModel`, `Field`, `ConfigDict`, `Discriminator`, `Tag`, `Annotated`), `typing` imports, `from enum import Enum`. Emit `parser_info()` function.

### `begin_class(classname, extends, doc, abstract, field_names, idfield, optional_fields)`

- Determine bases: `extends` names mapped to safe Python names, or `BaseModel` if no extends
- Emit `class Foo(Base1, Base2):` with docstring from `doc`
- If abstract: still emit the class with its own fields (not `pass`) — pydantic needs field declarations on the base
- Emit `model_config = ConfigDict(populate_by_name=True, extra="allow")`
- Store current class context for `declare_field()`

### `end_class(classname, field_names)`

Close class body. Track classname for `model_rebuild()` in epilogue.

### `declare_field(name, fieldtype, doc, optional, subscope)`

- **Skip if inherited**: if field has `inherited_from` and current class extends that parent, skip it
- Check for `pydantic:type` annotation — if present, use it verbatim as the type annotation
- Otherwise map `fieldtype.instance_type` to Python/pydantic type
- If field name differs from JSON key (e.g. `format_version` vs `format-version`): emit `Field(alias="format-version")`
- If optional: `field: Type | None = None`
- Emit field with `Field(description=...)` if doc present

### `declare_id_field(name, fieldtype, doc, optional)`

Emit as normal field (pydantic doesn't need schema-salad's UUID/baseuri machinery).

### `type_loader(type_declaration, container, no_link_check)`

Map schema-salad type declarations to `TypeDef` objects:
- Records: `TypeDef` with `instance_type` = class name
- Enums: single-symbol -> `Literal["value"]`, multi-symbol -> emit `Enum` class
- Arrays: `list[inner]`
- Unions: `inner1 | inner2`
- Primitives: direct Python type mapping

No runtime loader generation — pydantic handles validation.

### `uri_loader`, `idmap_loader`, `typedsl_loader`, `secondaryfilesdsl_loader`

All return inner unchanged. Pydantic doesn't need schema-salad's URI resolution, idmap, or DSL wrappers.

### `epilogue(root_loader)`

- Emit `model_rebuild()` calls for all classes (simpler than dependency analysis, safe with `from __future__ import annotations`)
- Emit deferred discriminator functions for fields with `pydantic:discriminator_map`
- Emit `load_document(path)` convenience function that reads JSON and validates against the document root model

## Enhanced Documentation

Schema-salad-doc renders `Any?` fields as `<a href="#Any">Any</a>` with no link to the actual intended type. The doc generator has no plugin system — type rendering is hardcoded in `makedoc.py`'s `RenderType.typefmt()` method.

**Approach: HTML post-processing** (extends the pattern already used in gxformat2's `build_schema.sh`).

Add a post-processing script that:
1. Parses the schema YAML to extract `pydantic:type` annotations
2. Builds a mapping: `(record_name, field_name) -> pydantic_type`
3. Finds `<a href="#Any">Any</a>` in the generated HTML within field rows
4. Replaces with rendered type info, linking to type definitions where possible (e.g. `<a href="#NativeStep">NativeStep</a>` within `dict[str, NativeStep]`)

This can live in this project as a reusable script/module, invoked from gxformat2's build script:

```bash
# In build_schema.sh after schema-salad-doc
python3 -m schema_salad_plus_pydantic enhance-docs schema/native_v0_1/workflow.yml "$out"
```

The type cell in schema-salad-doc HTML is always `<div class="col-xs-7 col-lg-3">`, making regex replacement reliable. We match by field name from the adjacent `<code>field_name</code>` cell to avoid false positives.

## CLI

```
schema-salad-plus-pydantic generate schema.yml -o models.py
schema-salad-plus-pydantic enhance-docs schema.yml docs.html -o docs_enhanced.html
```

## Tests

### `tests/schemas/simple.yml`

Minimal schema-salad schema with:
- A base record with fields (testing inheritance)
- A child record extending the base (testing field filtering)
- A multi-symbol enum
- A single-symbol discriminator enum
- A field with `pydantic:type` annotation
- A discriminated union with `pydantic:discriminator_field/map`
- A field with alias (hyphenated name)

### `test_codegen.py`

- Generate code from simple.yml -> assert valid Python (compile)
- Assert expected classes present
- Assert `pydantic:type` overrides appear in generated type annotations
- Assert discriminator functions generated
- Assert `Field(alias=...)` for aliased fields
- Assert enums generated correctly
- Assert inherited fields NOT redeclared on child classes
- Assert abstract base classes have their fields declared
- Assert `model_rebuild()` calls present in epilogue

### `test_roundtrip.py`

- Generate models from gxformat2's native_v0_1 schema (with annotations added)
- Import generated module dynamically
- Validate MINIMAL_WORKFLOW dict against generated model
- Validate dict-typed steps parse correctly
- Validate creator union dispatch works with real `class: "Person"` values
- Validate source_metadata loads
- Validate inheritance: NativeStep instance `isinstance()` checks against HasUUID etc.

## Resolved Questions

1. **`extend_and_specialize()` preserves unknown keys** — confirmed. `deepcopy_strip()` copies all dict items. `strict_foreign_properties=False` during validation. No pre-pass needed.

2. **Inheritance: proper pydantic class inheritance.** Abstract bases declare their fields. Children only declare new fields (filter by `inherited_from`). Multiple inheritance supported.

3. **`extra="allow"`** — use permissive mode. Matches real-world `.ga` files which may have undocumented fields. Can be made configurable later.

4. **Minimal reimplementation of orchestrator** (~80-100 lines). The codegen loop is stable, we only need record/enum/union handling + field sorting + optional detection + abstract/document-root handling. Skip all CWL-specific loader wrapping.

5. **`model_rebuild()` for all classes** — simpler than dependency analysis, no downside with `from __future__ import annotations`.

## Remaining Questions

1. Should `enhance-docs` be a subcommand of this CLI or a separate script for gxformat2's build process?
2. For generated discriminator functions, use pydantic's `Discriminator(callable)` or `Tag` annotation pattern?
3. Do we want to generate `model_validator` methods for cross-field constraints (e.g. source_metadata URL vs TRS mutual exclusivity)?
