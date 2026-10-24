@echo off
rem Starts Inventory & POS for the shop (v0.24.0): double-click this file.
rem It runs serve.py (the waitress server) with the project's own venv, from this folder.
rem First time on a computer: run "python setup_shop.py" (see README.md).
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo The venv folder is missing. Set the system up first: see README.md, "Quick start".
    pause
    exit /b 1
)
if not exist "instance\config.toml" (
    echo This computer has not been set up yet. Run:  venv\Scripts\python.exe setup_shop.py
    pause
    exit /b 1
)
"venv\Scripts\python.exe" serve.py
pause
