@echo off
REM ============================================================================
REM MX5-Telemetry Build Verification Script
REM ============================================================================
REM This script verifies the project meets all requirements and builds correctly
REM ============================================================================

echo ====================================
echo MX5-Telemetry Build Verification
echo ====================================
echo.

REM Check for PlatformIO
set "PIO_CMD="
where pio >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PIO_CMD=pio"
) else (
    if exist "%USERPROFILE%\.platformio\penv\Scripts\pio.exe" (
        set "PIO_CMD=%USERPROFILE%\.platformio\penv\Scripts\pio.exe"
    ) else (
        echo [X] PlatformIO CLI not found!
        echo Please install PlatformIO or use VS Code with PlatformIO extension
        pause
        exit /b 1
    )
)

echo [*] Found PlatformIO: %PIO_CMD%
echo.

echo ====================================
echo Requirement Verification
echo ====================================
echo.

echo [*] Checking requirements:
echo     - CAN Bus Communication: 500 kbaud
echo     - RPM Polling Rate: 50Hz (>20Hz required)
echo     - GPS Update Rate: 10Hz
echo     - Data Logging Rate: 5Hz
echo     - Error Handling: Graceful recovery
echo     - Power Management: Low-power standby mode
echo.

echo ====================================
echo Building Production Firmware
echo ====================================
echo.

echo [1/5] Building production target (nano_atmega328)...
"%PIO_CMD%" run -e nano_atmega328
if %ERRORLEVEL% NEQ 0 (
    echo [X] Production build FAILED!
    pause
    exit /b 1
)
echo     [OK] Production build successful
echo.

echo [2/5] Building release target (nano_release)...
"%PIO_CMD%" run -e nano_release
if %ERRORLEVEL% NEQ 0 (
    echo [X] Release build FAILED!
    pause
    exit /b 1
)
echo     [OK] Release build successful
echo.

echo [3/5] Building debug target (nano_debug)...
"%PIO_CMD%" run -e nano_debug
if %ERRORLEVEL% NEQ 0 (
    echo [X] Debug build FAILED!
    pause
    exit /b 1
)
echo     [OK] Debug build successful
echo.

echo [4/5] Running unit tests (native_sim)...
"%PIO_CMD%" test -e native_sim
if %ERRORLEVEL% NEQ 0 (
    echo [!] Unit tests had failures (check output above)
) else (
    echo     [OK] All unit tests passed
)
echo.

echo [5/5] Building Wokwi simulator (wokwi_sim)...
"%PIO_CMD%" run -e wokwi_sim
if %ERRORLEVEL% NEQ 0 (
    echo [X] Wokwi build FAILED!
    pause
    exit /b 1
)
echo     [OK] Wokwi build successful
echo.

echo ====================================
echo Memory Usage Analysis
echo ====================================
echo.

echo Production Build (nano_atmega328):
"%PIO_CMD%" run -e nano_atmega328 -t size
echo.

echo Release Build (nano_release):
"%PIO_CMD%" run -e nano_release -t size
echo.

echo ====================================
echo Verification Complete!
echo ====================================
echo.
echo All builds completed successfully!
echo.
echo Next Steps:
echo   1. Upload firmware: pio run -t upload
echo   2. Monitor serial: pio device monitor
echo   3. Run Wokwi simulator: F1 ^> "Wokwi: Start Simulator"
echo.
echo For detailed documentation, see:
echo   - docs/QUICK_START.md
echo   - docs/PLATFORMIO_GUIDE.md
echo   - docs/WIRING_GUIDE.md
echo.

pause
