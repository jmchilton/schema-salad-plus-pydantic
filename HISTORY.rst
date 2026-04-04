.. :changelog:

History
-------

.. to_doc

---------------------
0.1.9.dev0
---------------------


---------------------
0.1.8 (2026-04-04)
---------------------

* Fix multi-value ``Literal`` fields producing invalid ``default=`` in ``Field()`` (greedy regex captured all values instead of first).
* Fix TypeScript codegen for multi-value ``Literal`` types — now emits proper union types.


---------------------
0.1.7 (2026-04-04)
---------------------

* Add ``pydantic:discriminator_default`` annotation for fallback type resolution.
* Handle complex ``pydantic:type`` unions (e.g. ``list[A|B] | dict[str, A|B]``) — discriminator applied only to list branch.
* Dedup TypeScript/Effect Schema type guards for multi-value discriminator maps.
* Add ``--version`` flag to CLI.


---------------------
0.1.6 (2026-04-04)
---------------------

* Add identifier annotations to ``Schema.suspend()`` calls for ``JSONSchema.make()`` support.


---------------------
0.1.5 (2026-03-30)
---------------------

* Add TypeScript code generation backend.
* Add Effect Schema TypeScript code generation backend.
* Add TypeScript roundtrip tests using nodejs-wheel.

---------------------
0.1.4 (2026-03-24)
---------------------

* Fix nullable discriminated unions (``None | list[A | B]``) failing
  ``model_rebuild()`` in strict mode. Discriminator now correctly wraps
  only the inner union regardless of where ``None`` appears.
* Add tests for discriminator ``getattr`` with Python-safe attr names
  (``class_`` vs ``class``) and discriminated union model instance roundtrips.

---------------------
0.1.3 (2026-03-22)
---------------------

* Fix mypy errors in generated code: type discriminator function variables
  as ``str``, fix ``load_document`` return type for list comprehension.

---------------------
0.1.2 (2026-03-22)
---------------------

* Add ``--strict`` flag to emit models with ``extra="forbid"`` (reject unknown fields).
* Add ``enhance-docs`` command to post-process schema-salad-doc HTML with pydantic types.
* Add ``pydantic:discriminator_field`` / ``pydantic:discriminator_map`` support for
  discriminated unions with ``Annotated[..., Tag(...), Discriminator(...)]``.
* Lower minimum Python to 3.9; refactor ``match`` statements to ``if/elif``.
* Add ``pyyaml`` as explicit dependency for ``enhance-docs``.

---------------------
0.1.1 (2026-03-21)
---------------------


---------------------
0.1.0 (2026-03-21)
---------------------

* Initial implementation of pydantic v2 code generation from schema-salad definitions.
* Minimal orchestrator reimplementing schema-salad's ``codegen()`` loop for pydantic output.
* Support for ``pydantic:type``, ``pydantic:alias``, and ``pydantic:discriminator_*``
  schema annotations to express types schema-salad can't natively represent.
* Proper pydantic class inheritance — abstract bases declare fields, children inherit them.
* Multiple inheritance support (e.g. ``NativeStep(HasStepErrors, HasStepPosition, ...)``)
* Single-symbol enums emit as ``Literal["value"]`` with auto-defaults.
* Multi-symbol enums emit as ``str, Enum`` subclasses.
* ``Field(alias=...)`` for fields whose JSON key differs from the Python name.
* ``model_rebuild()`` calls for all classes to resolve forward references.
* ``load_document()`` convenience function for loading and validating JSON files.
* ``extra="allow"`` and ``populate_by_name=True`` on all models.
* CLI: ``schema-salad-plus-pydantic generate schema.yml -o models.py``

.. github_links
