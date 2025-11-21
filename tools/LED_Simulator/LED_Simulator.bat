@echo off
REM ============================================================================
REM LED Simulator Direct Launcher
REM ============================================================================

cd /d "%~dp0"
start "" "..\..\venv\Scripts\pythonw.exe" "led_simulator_v2.1.py"
