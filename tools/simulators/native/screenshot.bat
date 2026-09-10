@echo off
rem Build + render every screen to shot_0.bmp .. shot_7.bmp (no window).
setlocal
cd /d "%~dp0"
call "%~dp0build.bat"
if errorlevel 1 exit /b 1
echo.
echo Rendering screenshots...
"%~dp0esp32_ui_simulator.exe" --screenshot
