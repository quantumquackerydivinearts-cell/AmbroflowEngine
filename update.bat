@echo off
title Ko's Labyrinth - Update
cd /d "%~dp0"
echo Pulling latest code...
git pull
echo.
echo Syncing dependencies...
"%~dp0.venv\Scripts\pip.exe" install -r requirements.txt --quiet
echo.
echo Done. Close this window and launch the game normally.
pause