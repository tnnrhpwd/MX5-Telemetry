@echo off
REM ============================================================================
REM Create Desktop Shortcuts - Batch Launcher
REM ============================================================================
REM Run this to create shortcuts on your desktop
REM ============================================================================

echo.
echo ========================================================================
echo Creating Shortcuts for MX5-Telemetry Tools and Upload Scripts
echo ========================================================================
echo.

REM Run the VBScript to create shortcuts
cscript //nologo "%~dp0create_shortcuts.vbs"

if %errorlevel% equ 0 (
    echo.
    echo Shortcuts created successfully!
    echo.
    echo Build-Automation folder:
    echo   - Upload Master Arduino.lnk
    echo   - Upload Slave Arduino.lnk
    echo   - Upload Both Arduinos.lnk
    echo.
    echo Tools folder:
    echo   - LED Simulator.lnk
    echo   - Arduino Actions.lnk
    echo.
) else (
    echo.
    echo Failed to create shortcuts.
    echo.
)

pause
