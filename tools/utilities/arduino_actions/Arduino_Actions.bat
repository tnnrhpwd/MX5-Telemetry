@echo off
REM ============================================================================
REM Arduino Actions Direct Launcher
REM ============================================================================

cd /d "%~dp0"
start "" "..\..\..\venv\Scripts\pythonw.exe" "arduino_actions.py"
