.PHONY: install build lint format typecheck test all clean

.venv:
	python3 -m venv .venv

install: .venv
	.venv/bin/pip install -e ".[dev]"

build:
	.venv/bin/pip install build && .venv/bin/python -m build

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .

typecheck:
	.venv/bin/mypy src/renaimedia

test:
	.venv/bin/pytest

all: lint typecheck test

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
