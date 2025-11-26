@echo off
REM ============================================================================
REM Direct Arduino Nano Upload Script (CH340 chipset)
REM ============================================================================
REM This script uploads firmware directly using avrdude with optimal settings
REM for CH340-based Arduino Nano clones
REM ============================================================================

echo.
echo ========================================================================
echo Arduino Nano Firmware Upload (CH340)
echo ========================================================================
echo.

REM Set paths
set AVRDUDE=C:\Users\tanne\.platformio\packages\tool-avrdude\avrdude.exe
set AVRDUDE_CONF=C:\Users\tanne\.platformio\packages\tool-avrdude\avrdude.conf
set FIRMWARE=.pio\build\nano_atmega328_old\firmware.hex
set PORT=COM3
set BAUD=57600

REM Check if firmware exists
if not exist "%FIRMWARE%" (
    echo ERROR: Firmware not found: %FIRMWARE%
    echo Please build the project first: pio run -e nano_atmega328_old
    echo.
    pause
    exit /b 1
)

echo Found firmware: %FIRMWARE%
echo Using port: %PORT%
echo Baud rate: %BAUD%
echo.
echo INSTRUCTIONS:
echo 1. Make sure Arduino is plugged in
echo 2. Press ENTER to start upload
echo 3. When you see "Uploading...", press the RESET button on Arduino
echo.
pause

echo.
echo Uploading...
echo.

REM Upload with avrdude
"%AVRDUDE%" -C "%AVRDUDE_CONF%" -v -p atmega328p -c arduino -P %PORT% -b %BAUD% -D -U flash:w:"%FIRMWARE%":i

if %errorlevel% equ 0 (
    echo.
    echo ========================================================================
    echo SUCCESS! Firmware uploaded successfully
    echo ========================================================================
    echo.
) else (
    echo.
    echo ========================================================================
    echo UPLOAD FAILED - Error code: %errorlevel%
    echo ========================================================================
    echo.
    echo Try these steps:
    echo 1. Unplug and replug USB cable
    echo 2. Try a different USB port
    echo 3. Press reset button when "Uploading..." appears
    echo 4. Check COM port in Device Manager
    echo.
)

pause
