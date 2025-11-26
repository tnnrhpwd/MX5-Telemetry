@echo off
REM ============================================================================
REM Arduino Actions Launcher - Windows Batch Script
REM ============================================================================
REM Launches the Arduino Actions GUI tool for MX5-Telemetry control
REM ============================================================================

echo.
echo ========================================================================
echo Arduino Actions - USB Command Interface
echo ========================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from python.org
    echo.
    pause
    exit /b 1
)

REM Check if pyserial is installed
python -c "import serial" >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: pyserial package not found
    echo Installing pyserial...
    python -m pip install pyserial
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install pyserial
        echo Please run: pip install pyserial
        echo.
        pause
        exit /b 1
    )
    echo.
)

REM Launch Arduino Actions
echo Starting Arduino Actions...
echo.
python "%~dp0arduino_actions.py"

REM If script exits with error
if %errorlevel% neq 0 (
    echo.
    echo Arduino Actions exited with error code %errorlevel%
    pause
)
