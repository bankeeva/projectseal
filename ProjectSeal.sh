#!/bin/bash
# Запуск ProjectSeal на Linux без ввода команд в терминал.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x "dist/ProjectSeal/ProjectSeal" ]; then
  exec "dist/ProjectSeal/ProjectSeal"
fi

if [ -x ".venv/bin/python" ]; then
  exec ".venv/bin/python" "run_projectseal.pyw"
fi

exec python3 "run_projectseal.pyw"
