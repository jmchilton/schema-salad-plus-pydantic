.. :changelog:

History
-------

.. to_doc

---------------------
0.1.3.dev0
---------------------


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
