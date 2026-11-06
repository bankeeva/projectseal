#!/bin/bash
# Резервный запуск ProjectSeal на macOS двойным кликом.
# Для обычного пользователя предпочтителен ProjectSeal.app — он не открывает терминал.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  exec ".venv/bin/python" "run_projectseal.pyw"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "run_projectseal.pyw"
fi

osascript -e 'display dialog "Не найден Python 3. Установите готовую сборку ProjectSeal.app." with title "ProjectSeal" buttons {"OK"} default button "OK" with icon stop'
