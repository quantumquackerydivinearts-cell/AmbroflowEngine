@echo off
title Ko's Labyrinth
cd /d "%~dp0"
set PYTHONPATH=%~dp0
"%~dp0.venv\Scripts\python.exe" -m ambroflow
if errorlevel 1 (
    echo.
    echo  === Game exited with an error - see above ===
    pause
)