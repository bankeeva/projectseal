# Сборка ProjectSeal

Сборка выполняется **на целевой ОС**: PyInstaller не кросс-компилирует.

## macOS

```bash
bash packaging/build_macos.sh
# результат: dist/ProjectSeal.app
```

Требования: macOS 11+, Python 3.12+, интернет для установки зависимостей.
Приложение собирается с `console=False`, поэтому у пользователя нет терминала.
Для переноса на другой Mac:

```bash
ditto -c -k --sequesterRsrc --keepParent dist/ProjectSeal.app ProjectSeal-macOS.zip
```

Неподписанное приложение при первом запуске требует подтверждения Gatekeeper:
правый клик → «Открыть» → «Открыть» (или «Системные настройки → Конфиденциальность
и безопасность → Всё равно открыть»). Для коммерческого релиза нужна подпись и
нотаризация Apple Developer ID.

## Windows 10/11 x64

Запустите `packaging\build_windows.bat` (двойной клик). Скрипт создаст `.venv`,
установит зависимости и соберёт `dist\ProjectSeal.exe`.

Требования: Python 3.12 x64, интернет. Результат — один `.exe` без консоли.
Для распространения достаточно передать `ProjectSeal.exe`; `ProjectSeal.vbs`
нужен только как резервный запуск из исходников.

SmartScreen для неподписанного exe: «Подробнее» → «Выполнить в любом случае».
Для коммерческого релиза нужна подпись кода (Authenticode).

## Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean packaging/ProjectSeal.spec
# результат: dist/ProjectSeal/ProjectSeal
```

## Проверка сборки

```bash
# Из исходников:
python run_projectseal.pyw --self-check

# У собранного macOS-приложения:
PROJECTSEAL_SELF_CHECK_OUT="$PWD/selfcheck.json" \
  dist/ProjectSeal.app/Contents/MacOS/ProjectSeal --self-check
```

Самопроверка проверяет доступность `rules.json`, иконок, сканера и экспортёра
внутри frozen-сборки. Обычному пользователю этот флаг не нужен.
