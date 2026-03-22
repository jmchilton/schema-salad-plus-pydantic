SOURCE_DIR?=src/schema_salad_plus_pydantic
TEST_DIR?=tests
BUILD_SCRIPTS_DIR=scripts
UPSTREAM?=origin
VERSION?=$(shell uv run --group release python3 $(BUILD_SCRIPTS_DIR)/print_version_for_release.py $(SOURCE_DIR))

.PHONY: help clean setup-venv test lint lint-fix format mypy dist commit-version new-version release-local push-release release add-history

help: ## show this help
	@egrep '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

clean: ## remove build/test artifacts
	rm -rf build/ dist/ *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov/
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +

setup-venv: ## sync dev environment with uv
	uv sync --group test --group lint --group mypy

test: ## run tests
	uv run --group test pytest $(TEST_DIR) -x -q

lint: ## run ruff and black checks
	uv run --group lint ruff check $(SOURCE_DIR) $(TEST_DIR)
	uv run --group lint black --check --diff $(SOURCE_DIR) $(TEST_DIR)

lint-fix: ## auto-fix lint issues
	uv run --group lint ruff check --fix $(SOURCE_DIR) $(TEST_DIR)
	uv run --group lint black $(SOURCE_DIR) $(TEST_DIR)

format: ## format code with black
	uv run --group lint black $(SOURCE_DIR) $(TEST_DIR)

mypy: ## run type checking
	uv run --group mypy mypy $(SOURCE_DIR)

dist: clean ## create and check packages
	uv run --group release python3 -m build
	uv run --group release twine check dist/*
	ls -l dist

commit-version: ## update version and history, commit and tag
	uv run --group release python3 $(BUILD_SCRIPTS_DIR)/commit_version.py $(SOURCE_DIR) $(VERSION)

new-version: ## bump to next patch dev version
	uv run --group release python3 $(BUILD_SCRIPTS_DIR)/new_version.py $(SOURCE_DIR) --patch

release-local: commit-version new-version ## commit release + start next dev

push-release: ## push main and tags to upstream
	git push $(UPSTREAM) main
	git push --tags $(UPSTREAM)

release: release-local dist push-release ## full release: tag, build, push

add-history: ## generate acknowledgements from merge commits
	uv run --group release python3 $(BUILD_SCRIPTS_DIR)/bootstrap_history.py --acknowledgements
