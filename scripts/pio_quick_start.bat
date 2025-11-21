@echo off
REM ============================================================================
REM Quick PlatformIO Setup and Test Script for MX5-Telemetry
REM ============================================================================

echo ==========================================
echo MX5-Telemetry PlatformIO Quick Start
echo ==========================================
echo.

REM Try to find PlatformIO CLI
set "PIO_CMD="
where pio >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PIO_CMD=pio"
    echo [✓] Found 'pio' in PATH
) else (
    REM Try default PlatformIO location
    if exist "%USERPROFILE%\.platformio\penv\Scripts\pio.exe" (
        set "PIO_CMD=%USERPROFILE%\.platformio\penv\Scripts\pio.exe"
        echo [✓] Found PlatformIO in default location
    ) else (
        echo [✗] PlatformIO CLI not found!
        echo.
        echo PlatformIO is installed but not in your PATH.
        echo.
        echo OPTION 1: Use VS Code GUI instead ^(EASIEST^)
        echo   1. Open this folder in VS Code
        echo   2. Click PlatformIO icon ^(alien head^) in sidebar
        echo   3. Use GUI buttons for Build/Upload/Test
        echo.
        echo OPTION 2: Add PlatformIO to PATH
        echo   Add this to your PATH:
        echo   %USERPROFILE%\.platformio\penv\Scripts
        echo.
        echo OPTION 3: Run from VS Code terminal
        echo   1. Open VS Code
        echo   2. Press Ctrl+` to open terminal
        echo   3. Run: pio --version
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Using: %PIO_CMD%
echo.

REM Show menu
:menu
echo What would you like to do?
echo.
echo   1. Install libraries and build project
echo   2. Run unit tests (simulation)
echo   3. Build and upload to Arduino Nano
echo   4. Build for Wokwi simulator
echo   5. Open serial monitor
echo   6. Clean build files
echo   0. Exit
echo.
choice /c 1234560 /n /m "Select option (1-6, 0 to exit): "

if errorlevel 7 goto end
if errorlevel 6 goto clean
if errorlevel 5 goto monitor
if errorlevel 4 goto wokwi
if errorlevel 3 goto upload
if errorlevel 2 goto test
if errorlevel 1 goto build

:build
echo.
echo ==========================================
echo Building MX5-Telemetry for Arduino Nano
echo ==========================================
echo.
"%PIO_CMD%" lib install
"%PIO_CMD%" run -e nano_atmega328
echo.
if %ERRORLEVEL% EQU 0 (
    echo [✓] Build successful!
) else (
    echo [✗] Build failed! Check errors above.
)
echo.
pause
goto menu

:test
echo.
echo ==========================================
echo Running Unit Tests
echo ==========================================
echo.
"%PIO_CMD%" test -e native_sim -v
echo.
if %ERRORLEVEL% EQU 0 (
    echo [✓] All tests passed!
) else (
    echo [✗] Some tests failed! Check output above.
)
echo.
pause
goto menu

:upload
echo.
echo ==========================================
echo Building and Uploading to Arduino Nano
echo ==========================================
echo.
echo Make sure Arduino Nano is connected via USB!
echo.
pause
"%PIO_CMD%" run -e nano_atmega328 --target upload
echo.
if %ERRORLEVEL% EQU 0 (
    echo [✓] Upload successful!
    echo.
    echo Open serial monitor to view output? (Y/N)
    choice /c YN /n
    if errorlevel 2 goto menu
    if errorlevel 1 goto monitor
) else (
    echo [✗] Upload failed! Check connection and try again.
    echo.
    pause
)
goto menu

:wokwi
echo.
echo ==========================================
echo Building for Wokwi Simulator
echo ==========================================
echo.
"%PIO_CMD%" run -e wokwi_sim
echo.
if %ERRORLEVEL% EQU 0 (
    echo [✓] Build successful!
    echo.
    echo To start simulation:
    echo   1. Install Wokwi extension in VS Code
    echo   2. Press F1 and type "Wokwi: Start Simulator"
    echo   3. OR click "Start Simulation" in Wokwi panel
) else (
    echo [✗] Build failed! Check errors above.
)
echo.
pause
goto menu

:monitor
echo.
echo ==========================================
echo Opening Serial Monitor (115200 baud)
echo ==========================================
echo.
echo Press Ctrl+C to exit monitor
echo.
timeout /t 2
"%PIO_CMD%" device monitor --baud 115200
goto menu

:clean
echo.
echo ==========================================
echo Cleaning Build Files
echo ==========================================
echo.
"%PIO_CMD%" run --target cleanall
echo [✓] Clean complete!
echo.
pause
goto menu

:end
echo.
echo Goodbye!
echo.
timeout /t 1
exit /b 0
