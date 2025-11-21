@echo off
REM ============================================================================
REM Arduino Library Installation Script for MX5-Telemetry
REM ============================================================================
REM This script helps install required Arduino libraries using arduino-cli
REM If you don't have arduino-cli, use Arduino IDE Library Manager instead
REM ============================================================================

echo ====================================
echo MX5-Telemetry Library Installer
echo ====================================
echo.

REM Check if arduino-cli is installed
where arduino-cli >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: arduino-cli not found!
    echo.
    echo Please install arduino-cli from: https://arduino.github.io/arduino-cli/
    echo.
    echo OR use Arduino IDE Library Manager:
    echo   1. Open Arduino IDE
    echo   2. Go to: Tools ^> Manage Libraries
    echo   3. Search and install:
    echo      - MCP_CAN ^(by Cory J. Fowler^)
    echo      - Adafruit NeoPixel ^(by Adafruit^)
    echo      - TinyGPSPlus ^(by Mikal Hart^)
    echo.
    pause
    exit /b 1
)

echo Found arduino-cli! Installing libraries...
echo.

REM Update library index
echo [1/4] Updating library index...
arduino-cli lib update-index
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to update library index
    pause
    exit /b 1
)
echo     Done!
echo.

REM Install MCP_CAN library
echo [2/4] Installing MCP_CAN library...
arduino-cli lib install "MCP_CAN"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: MCP_CAN installation failed, trying alternative name...
    arduino-cli lib install "MCP_CAN_lib"
)
echo     Done!
echo.

REM Install Adafruit NeoPixel library
echo [3/4] Installing Adafruit NeoPixel library...
arduino-cli lib install "Adafruit NeoPixel"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Adafruit NeoPixel installation failed
    pause
    exit /b 1
)
echo     Done!
echo.

REM Install TinyGPSPlus library
echo [4/4] Installing TinyGPSPlus library...
arduino-cli lib install "TinyGPSPlus"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: TinyGPSPlus installation failed
    pause
    exit /b 1
)
echo     Done!
echo.

echo ====================================
echo Installation Complete!
echo ====================================
echo.
echo Installed libraries:
arduino-cli lib list | findstr /I "MCP_CAN NeoPixel TinyGPS"
echo.
echo Built-in libraries (no installation needed):
echo   - SPI
echo   - SD
echo   - SoftwareSerial
echo.
echo You can now compile MX5_Telemetry.ino in Arduino IDE!
echo.
pause
