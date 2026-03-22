# schema-salad-plus-pydantic

Generate [pydantic v2](https://docs.pydantic.dev/) `BaseModel` classes from
[schema-salad](https://www.commonwl.org/v1.2/SchemaSalad.html) definitions.

## What it does

Schema-salad defines record types, enums, inheritance, and unions in YAML.
This tool reads those definitions and emits a Python module of pydantic
`BaseModel` classes that can validate, parse, and serialize data conforming
to the schema.

Key features:

- **Proper pydantic inheritance** -- abstract bases declare fields, children
  inherit them, multiple inheritance works naturally.
- **Schema annotations** for types schema-salad can't express natively:
  - `pydantic:type` -- override the generated type annotation (e.g. `dict[str, NativeStep]`)
  - `pydantic:alias` -- set a Field alias for JSON keys that differ from the Python name
  - `pydantic:discriminator_field` / `pydantic:discriminator_map` -- discriminated unions
- **Enums** -- multi-symbol enums become `str, Enum` classes; single-symbol
  enums become `Literal["value"]` with auto-defaults.
- **Forward references** -- `model_rebuild()` for all classes, `from __future__ import annotations`.
- **Permissive by default** -- `extra="allow"`, `populate_by_name=True`.

## Installation

```bash
pip install schema-salad-plus-pydantic
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install schema-salad-plus-pydantic
```

## Usage

### CLI

Generate pydantic models from a schema-salad YAML file:

```bash
schema-salad-plus-pydantic generate schema.yml -o models.py
```

Pass `--strict` to emit models with `extra="forbid"` (reject unknown JSON keys); the default is permissive `extra="allow"`.

Or write to stdout:

```bash
schema-salad-plus-pydantic generate schema.yml > models.py
```

### Python API

```python
from io import StringIO
from schema_salad_plus_pydantic.orchestrate import generate_from_schema

buf = StringIO()
generate_from_schema("path/to/schema.yml", buf)
code = buf.getvalue()

# Or write directly to a file
with open("models.py", "w") as f:
    generate_from_schema("path/to/schema.yml", f)

# Optional: strict=True emits models with extra="forbid" (unknown keys rejected)
with open("models_strict.py", "w") as f:
    generate_from_schema("path/to/schema.yml", f, strict=True)
```

### Using the generated models

```python
import json
from generated_models import MyRecord  # the module you generated

# Validate a dict
obj = MyRecord.model_validate({"field": "value", "count": 42})

# Validate from JSON
with open("data.json") as f:
    obj = MyRecord.model_validate(json.load(f))

# Access fields
print(obj.field)
print(obj.count)

# Serialize back to dict/JSON
print(obj.model_dump())
print(obj.model_dump_json(indent=2))
```

### Schema annotations

Add `pydantic:*` keys to schema-salad field definitions to control the
generated type annotations. Requires a `pydantic` namespace declaration:

```yaml
$namespaces:
  pydantic: "https://example.org/pydantic#"

$graph:
- name: MyRecord
  type: record
  fields:
    - name: steps
      type: Any?
      pydantic:type: "dict[str, Step]"

    - name: format_version
      type: string
      pydantic:alias: "format-version"

    - name: creator
      type: Any?
      pydantic:type: "list[Person | Organization] | None"
      pydantic:discriminator_field: "class"
      pydantic:discriminator_map: '{"Person": "Person", "Organization": "Organization"}'
```

## Development

Setup with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group test --group lint --group mypy
```

Run checks:

```bash
make test         # pytest
make lint         # ruff + black
make mypy         # type checking
```

## Releasing

See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Quick version:

```bash
make add-history  # generate PR acknowledgements in HISTORY.rst
make release      # tag, build, push (triggers PyPI publish via GitHub Actions)
```

## License

MIT -- see [LICENSE](LICENSE).
