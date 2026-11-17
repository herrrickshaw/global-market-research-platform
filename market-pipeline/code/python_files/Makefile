# Makefile -- reusable entry points for the dev-tooling stack in pyproject.toml.
# Run `make help` for the list. Install the tools first with `make install-dev`.
#
# Design: `format`/`lint` are the two you run locally and they WRITE changes.
# Everything else (lint-check/typecheck/security/duplicates) is report-only --
# safe to run any time, never touches your files.

.PHONY: help install-dev test test-fast format lint lint-check typecheck security duplicates duplicates-jscpd check-all

# The pipeline's own interpreter, never PATH python3 (see daily_mailer.sh:93).
PY ?= .venv/bin/python3

help:
	@echo "install-dev       pip install the pinned tool versions (requirements-dev.txt)"
	@echo "test              pytest tests/ -- send gates, session clock, mailer lock (hermetic, ~1 min)"
	@echo "test-fast         same minus the sandboxed daily_mailer.sh runs (~5 s)"
	@echo "format            ruff format .                (writes)"
	@echo "lint              ruff check --fix .            (writes)"
	@echo "lint-check        ruff check .                  (report only)"
	@echo "typecheck         mypy .                         (report only)"
	@echo "security          bandit -r .                    (report only)"
	@echo "duplicates        pylint --enable=duplicate-code  (report only, AST-aware)"
	@echo "duplicates-jscpd  jscpd .                         (report only, token-based, needs npx)"
	@echo "check-all         lint-check + typecheck + security + duplicates, no writes"

install-dev:
	pip install -r requirements-dev.txt

# Hermetic: no network, no Postgres/Cassandra, no real scan workbooks, no email.
# Every external seam is monkeypatched in tests/conftest.py and the per-file
# fixtures; the shell tests copy daily_mailer.sh into a sandbox with a stub venv.
test:
	$(PY) -m pytest tests/ -q -p no:cacheprovider

test-fast:
	$(PY) -m pytest tests/ -q -p no:cacheprovider --ignore=tests/test_daily_mailer_sh.py

format:
	ruff format .

lint:
	ruff check --fix .

lint-check:
	ruff check .

typecheck:
	mypy .

security:
	bandit -r . -c pyproject.toml

duplicates:
	pylint --disable=all --enable=duplicate-code $$(git ls-files '*.py')

duplicates-jscpd:
	npx --yes jscpd@latest . --min-lines 10 --min-tokens 70 \
		--ignore "**/cache_seed/**,**/docs_cache/**,**/*.ipynb"

check-all: lint-check typecheck security duplicates
	@echo "Done -- report-only, nothing written. Run 'make format' / 'make lint' to fix what's auto-fixable."
