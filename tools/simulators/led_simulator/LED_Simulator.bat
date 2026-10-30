@echo off
REM ============================================================================
REM MX5-Telemetry LED simulator - double-click launcher
REM ============================================================================
REM Runs led_simulator_v3.py with pythonw so no console window sits behind the
REM GUI. Any arguments given here are passed through, e.g.:
REM     LED_Simulator.bat --leds 30
REM     LED_Simulator.bat --pi 192.168.42.100:5000
REM ============================================================================

cd /d "%~dp0"

set "PYW="
if exist "..\..\..\venv\Scripts\pythonw.exe" set "PYW=..\..\..\venv\Scripts\pythonw.exe"
if not defined PYW (
    where pythonw >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PYW=pythonw"
)

if not defined PYW (
    echo [X] No Python found.
    echo.
    echo Install Python 3.8+ from https://www.python.org/downloads/ and tick
    echo "Add Python to PATH", or create the project venv:
    echo     py -m venv venv
    pause
    exit /b 1
)

start "" "%PYW%" "led_simulator_v3.py" %*
