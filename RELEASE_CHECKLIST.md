# Release Checklist

This checklist mirrors the release process used by
[Planemo](https://github.com/galaxyproject/planemo).

## Pre-release

- [ ] Ensure all CI checks pass on `main`
- [ ] Run `make add-history` to generate acknowledgements from merge commits
- [ ] Review and edit `HISTORY.rst` — clean up entries, ensure all notable
      changes are documented
- [ ] Run full test suite locally: `make test`
- [ ] Run lint and type checks: `make lint && make mypy`

## Release

- [ ] Run `make release-local` — this will:
  - Strip `.dev0` from version, date the release in `HISTORY.rst`
  - Commit and tag the release
  - Bump to next patch `.dev0`, commit
- [ ] Verify the packages build cleanly: `make dist`
- [ ] Push the release: `make push-release`
  - This pushes `main` and tags to the upstream remote
  - The `deploy.yaml` workflow will publish to PyPI on tag push

## Post-release

- [ ] Verify the package appears on [PyPI](https://pypi.org/project/schema-salad-plus-pydantic/)
- [ ] Verify the GitHub Actions deploy workflow completed successfully
- [ ] Announce if appropriate

## Quick release (all-in-one)

```bash
make release
```

This runs: `release-local` -> `dist` -> `push-release`
