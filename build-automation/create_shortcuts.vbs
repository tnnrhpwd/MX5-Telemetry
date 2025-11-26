' ============================================================================
' Create Shortcuts for MX5-Telemetry Tools and Upload Scripts
' ============================================================================
' Creates shortcuts in appropriate folders:
' - Upload scripts in build-automation/
' - Tool shortcuts in tools/
' ============================================================================

Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the project root directory (parent of build-automation)
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(scriptDir)

' Folder paths
buildAutomationPath = projectRoot & "\build-automation"
toolsPath = projectRoot & "\tools"

' Python executable path
pythonExe = projectRoot & "\venv\Scripts\pythonw.exe"

' Check if virtual environment exists
If Not fso.FileExists(pythonExe) Then
    MsgBox "Virtual environment not found!" & vbCrLf & _
           "Expected: " & pythonExe & vbCrLf & vbCrLf & _
           "Please run setup first.", vbCritical, "Error"
    WScript.Quit
End If

' ============================================================================
' Create Upload Shortcuts in build-automation folder
' ============================================================================

' Upload Master Arduino
Set link = WshShell.CreateShortcut(buildAutomationPath & "\Upload Master Arduino.lnk")
link.TargetPath = "powershell.exe"
link.Arguments = "-ExecutionPolicy Bypass -File """ & buildAutomationPath & "\upload_master.ps1"""
link.WorkingDirectory = projectRoot
link.Description = "Upload firmware to Master Arduino (Telemetry Logger)"
link.IconLocation = "imageres.dll,1"
link.Save

' Upload Slave Arduino
Set link = WshShell.CreateShortcut(buildAutomationPath & "\Upload Slave Arduino.lnk")
link.TargetPath = "powershell.exe"
link.Arguments = "-ExecutionPolicy Bypass -File """ & buildAutomationPath & "\upload_slave.ps1"""
link.WorkingDirectory = projectRoot
link.Description = "Upload firmware to Slave Arduino (LED Controller)"
link.IconLocation = "imageres.dll,1"
link.Save

' Upload Both Arduinos
Set link = WshShell.CreateShortcut(buildAutomationPath & "\Upload Both Arduinos.lnk")
link.TargetPath = "powershell.exe"
link.Arguments = "-ExecutionPolicy Bypass -File """ & buildAutomationPath & "\upload_both.ps1"""
link.WorkingDirectory = projectRoot
link.Description = "Upload firmware to both Master and Slave Arduinos"
link.IconLocation = "imageres.dll,1"
link.Save

' ============================================================================
' Create Tool Shortcuts in tools folder
' ============================================================================

' LED Simulator
Set link = WshShell.CreateShortcut(toolsPath & "\LED Simulator.lnk")
link.TargetPath = pythonExe
link.Arguments = """" & projectRoot & "\tools\simulators\led_simulator\led_simulator_v2.1.py"""
link.WorkingDirectory = projectRoot & "\tools\simulators\led_simulator"
link.Description = "MX5-Telemetry LED Simulator v2.1"
link.IconLocation = pythonExe & ",0"
link.Save

' Arduino Actions
Set link = WshShell.CreateShortcut(toolsPath & "\Arduino Actions.lnk")
link.TargetPath = pythonExe
link.Arguments = """" & projectRoot & "\tools\utilities\arduino_actions\arduino_actions.py"""
link.WorkingDirectory = projectRoot & "\tools\utilities\arduino_actions"
link.Description = "MX5-Telemetry Arduino Actions Utility"
link.IconLocation = pythonExe & ",0"
link.Save

' Success message
MsgBox "Shortcuts created successfully!" & vbCrLf & vbCrLf & _
       "Build-Automation folder:" & vbCrLf & _
       "  - Upload Master Arduino.lnk" & vbCrLf & _
       "  - Upload Slave Arduino.lnk" & vbCrLf & _
       "  - Upload Both Arduinos.lnk" & vbCrLf & vbCrLf & _
       "Tools folder:" & vbCrLf & _
       "  - LED Simulator.lnk" & vbCrLf & _
       "  - Arduino Actions.lnk", vbInformation, "Success"
