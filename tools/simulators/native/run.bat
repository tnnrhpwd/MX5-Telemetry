@echo off
rem Build + launch the interactive ESP32-S3 UI simulator.
setlocal
cd /d "%~dp0"
call "%~dp0build.bat"
if errorlevel 1 exit /b 1
echo.
echo Launching simulator (press H for help, Q to quit)...
"%~dp0esp32_ui_simulator.exe"
