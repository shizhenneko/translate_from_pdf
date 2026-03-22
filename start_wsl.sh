#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PORT="${1:-10001}"

if [[ $# -gt 0 ]]; then
  shift
fi

pick_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return
  fi
  if command -v python3.10 >/dev/null 2>&1; then
    echo "python3.10"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  echo "python" 
}

PYTHON_BIN="$(pick_python)"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pip install marker-pdf

exec python -m pdf_translate serve --host 127.0.0.1 --port "${PORT}" "$@"
