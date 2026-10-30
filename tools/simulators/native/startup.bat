@echo off
rem Build + render the power-on sequence to boot_*.bmp, the Pi wait to
rem wait_*.bmp and the live Overview to live_*.bmp (no window).
setlocal
cd /d "%~dp0"
call "%~dp0build.bat"
if errorlevel 1 exit /b 1
echo.
echo Rendering boot sequence...
"%~dp0esp32_ui_simulator.exe" --startup
