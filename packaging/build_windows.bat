@echo off
rem Сборка ProjectSeal.exe на Windows 10/11 x64. Запускать на Windows.
setlocal
cd /d "%~dp0.."

if not exist ".venv" (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3.12 -m venv .venv
  ) else (
    python -m venv .venv
  )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

pyinstaller --noconfirm --clean packaging\ProjectSeal.spec
if errorlevel 1 goto :error

echo.
echo Готово: dist\ProjectSeal.exe
echo Для передачи пользователю положите рядом ProjectSeal.vbs (необязательно).
pause
exit /b 0

:error
echo.
echo Сборка не удалась. Проверьте, что установлен Python 3.12 x64 и есть интернет.
pause
exit /b 1
