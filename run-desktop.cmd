@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m cad_agent gui
if errorlevel 1 pause
