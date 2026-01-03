#!/usr/bin/env bash
set -euo pipefail

mypy src/ --strict
ruff check src/ tests/ --select=E9,F63,F7,F82
pytest tests/ "$@"
