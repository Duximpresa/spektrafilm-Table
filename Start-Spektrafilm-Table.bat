@echo off
setlocal
cd /d "%~dp0"
title spektrafilm-Table

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Python environment not found: .venv\Scripts\python.exe
    echo Please follow the installation instructions in README.md first.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" -m spektrafilm_gui.table_app %*
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
    echo.
    echo [ERROR] spektrafilm-Table exited with code %launch_exit%.
    pause
)
exit /b %launch_exit%
