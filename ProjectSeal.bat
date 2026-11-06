@echo off
rem Резервный запуск ProjectSeal на Windows.
rem Для обычного пользователя используйте ProjectSeal.exe или ProjectSeal.vbs.
cd /d "%~dp0"

if exist "ProjectSeal.exe" (
  start "" "ProjectSeal.exe"
  exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "run_projectseal.pyw"
  exit /b 0
)

where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw.exe "run_projectseal.pyw"
  exit /b 0
)

echo Не найден ProjectSeal.exe и не установлен Python.
echo Скачайте готовую сборку ProjectSeal для Windows.
pause
exit /b 1
