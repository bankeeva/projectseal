#!/bin/bash
# Сборка ProjectSeal.app на macOS. Запускать на macOS.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
if [ ! -d ".venv" ]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source ".venv/bin/activate"
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

pyinstaller --noconfirm --clean packaging/ProjectSeal.spec

echo
echo "Готово: dist/ProjectSeal.app"
echo "Для переноса на другой Mac: zip -r ProjectSeal-macOS.zip dist/ProjectSeal.app"
