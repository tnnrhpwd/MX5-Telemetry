@echo off
REM ============================================================================
REM Create Desktop Shortcuts - Batch Launcher
REM ============================================================================
REM Run this to create shortcuts on your desktop
REM ============================================================================

echo.
echo ========================================================================
echo Creating Desktop Shortcuts for MX5-Telemetry Tools
echo ========================================================================
echo.

REM Run the VBScript to create shortcuts
cscript //nologo "%~dp0create_shortcuts.vbs"

if %errorlevel% equ 0 (
    echo.
    echo Shortcuts created successfully!
    echo Check your desktop for:
    echo   - LED Simulator.lnk
    echo   - Arduino Actions.lnk
    echo.
) else (
    echo.
    echo Failed to create shortcuts.
    echo.
)

pause
