#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "error: Python interpreter not found at $PYTHON_BIN"
  echo "hint: create venv with 'uv venv .venv' and install dependencies with 'uv sync'"
  exit 1
fi

cd "$ROOT_DIR"
PYTHONPATH=src "$PYTHON_BIN" -m unittest discover -s tests -v
