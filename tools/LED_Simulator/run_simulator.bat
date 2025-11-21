@echo off
REM ============================================================================
REM MX5-Telemetry LED Simulator Launcher (Windows)
REM ============================================================================
REM This script launches the LED simulator for testing LED logic before upload
REM ============================================================================

echo ====================================
echo MX5-Telemetry LED Simulator
echo ====================================
echo.

REM Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python not found!
    echo.
    echo Please install Python 3.7 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [*] Python found
echo.

REM Check if we're in the right directory
if not exist "tools\LED_Simulator\led_simulator_v2.1.py" (
    echo [X] Error: Must run from project root directory
    echo.
    echo Current directory: %CD%
    echo Expected: MX5-Telemetry root folder
    pause
    exit /b 1
)

echo [*] Launching LED Simulator...
echo.
echo Controls:
echo   - Arrow Up: Gas Pedal
echo   - Arrow Down: Brake
echo   - Arrow Right: Shift Up
echo   - Arrow Left: Shift Down
echo   - Shift Key: Clutch
echo   - ESC: Quit
echo.

REM Launch the simulator
python tools\LED_Simulator\led_simulator_v2.1.py

echo.
echo Simulator closed.
pause
