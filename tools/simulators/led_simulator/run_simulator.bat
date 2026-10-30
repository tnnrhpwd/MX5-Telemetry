@echo off
REM ============================================================================
REM MX5-Telemetry LED simulator launcher (Windows), for running from anywhere
REM ============================================================================
REM Keeps a console open so anything the simulator prints is visible. Arguments
REM are passed through, e.g.  run_simulator.bat --leds 30
REM ============================================================================

set "HERE=%~dp0"
set "PY="
if exist "%HERE%..\..\..\venv\Scripts\python.exe" set "PY=%HERE%..\..\..\venv\Scripts\python.exe"
if not defined PY (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PY=python"
)
if not defined PY (
    echo [X] Python not found. Install Python 3.8+ and tick "Add Python to PATH".
    pause
    exit /b 1
)

echo MX5-Telemetry LED simulator
echo.
echo   Up / Down        +/- 100 rpm
echo   PageUp / PageDn  +/- 500 rpm
echo   Home / End       0 and full rpm
echo   Space            auto-sweep
echo   S / M / E        sequence / color mode / strip on-off
echo   T / I            self test / identify
echo   Esc              quit
echo.

"%PY%" "%HERE%led_simulator_v3.py" %*
if %ERRORLEVEL% NEQ 0 pause
