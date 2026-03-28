# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Code generator that reads schema-salad YAML definitions and emits pydantic v2 `BaseModel` classes. Supports `pydantic:type`, `pydantic:alias`, `pydantic:discriminator_field`, and `pydantic:discriminator_map` annotations on schema fields.

## Commands

```bash
uv sync --group test --group lint --group mypy   # setup
make test                                         # pytest -x -q
make lint                                         # ruff + black
make lint-fix                                     # auto-fix
make mypy                                         # type check
make format                                       # black only

# run single test
uv run --group test pytest tests/test_codegen.py::test_generates_valid_python -x -q
```

## Architecture

**`orchestrate.py`** — entry point. Loads schema-salad YAML via `schema_salad.schema.get_metaschema()`, runs `extend_and_specialize()`, then drives a two-pass loop over records/enums. Extracts `pydantic:*` annotations from field dicts and feeds them to the code generator. `generate_from_schema()` is the public Python API.

**`codegen.py`** — `PydanticCodeGen` class. Mirrors `CodeGenBase` interface but does NOT subclass it (Cython `.so` blocks subclassing). Emits enum classes, model classes, discriminator functions, `model_rebuild()` calls, and `load_document()`. Key design choices:
- Abstract bases declare their fields; children skip inherited fields (checked via `inherited_from`)
- Loader methods (`uri_loader`, `idmap_loader`, `typedsl_loader`) are no-ops — pydantic handles validation
- Enums: multi-symbol → `str, Enum`; single-symbol → `Literal["value"]` with auto-default
- Two `StringIO` buffers (`_enum_code`, `_class_code`) allow enums to be emitted before classes in the final output

**`enhance_docs.py`** — HTML post-processor for schema-salad-doc output. Replaces `Any` type cells with actual pydantic types and links.

**`cli.py`** — `generate` and `enhance-docs` subcommands.

## Test Structure

- `test_codegen.py` — generates code from `tests/schemas/simple.yml`, checks structure (classes, enums, inheritance, aliases, discriminators, strict mode)
- `test_roundtrip.py` — generates code, dynamically imports it, validates data against models. Some tests require an external gxformat2 checkout (controlled by `GXFORMAT2_SCHEMA_DIR` env var, skipped if absent)
- Tests compile+exec generated code via `importlib.util` to test runtime behavior

## Style

- Line length: 120 (black + ruff)
- Target: Python 3.9+
- `from __future__ import annotations` everywhere
- ruff rules: E, F, W, I, UP
