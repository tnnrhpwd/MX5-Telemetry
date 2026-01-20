@echo off
REM Quick launcher for ESP32-S3 Live Display Simulator
REM Double-click this file to start the simulator

echo ========================================
echo ESP32-S3 Live Display Simulator
echo ========================================
echo.

cd /d "%~dp0..\.."

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    echo.
    pause
    exit /b 1
)

REM Check if pygame is installed
venv\Scripts\python.exe -c "import pygame" 2>nul
if errorlevel 1 (
    echo Installing required dependencies...
    venv\Scripts\python.exe -m pip install pygame watchdog
    echo.
)

REM Launch simulator
echo Starting simulator...
echo.
venv\Scripts\python.exe tools\simulators\esp32_live_simulator.py

pause
