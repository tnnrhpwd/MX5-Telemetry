' ============================================================================
' Create Desktop Shortcuts for MX5-Telemetry Tools
' ============================================================================
' Double-click this file to create shortcuts on your desktop
' ============================================================================

Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the script directory (project root)
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopPath = WshShell.SpecialFolders("Desktop")

' Python executable path
pythonExe = scriptDir & "\venv\Scripts\pythonw.exe"

' Check if virtual environment exists
If Not fso.FileExists(pythonExe) Then
    MsgBox "Virtual environment not found!" & vbCrLf & _
           "Expected: " & pythonExe & vbCrLf & vbCrLf & _
           "Please run setup first.", vbCritical, "Error"
    WScript.Quit
End If

' ============================================================================
' Create LED Simulator Shortcut
' ============================================================================
Set link = WshShell.CreateShortcut(desktopPath & "\LED Simulator.lnk")
link.TargetPath = pythonExe
link.Arguments = """" & scriptDir & "\tools\LED_Simulator\led_simulator_v2.1.py"""
link.WorkingDirectory = scriptDir & "\tools\LED_Simulator"
link.Description = "MX5-Telemetry LED Simulator"
link.IconLocation = pythonExe & ",0"
link.Save

' ============================================================================
' Create Arduino Actions Shortcut
' ============================================================================
Set link = WshShell.CreateShortcut(desktopPath & "\Arduino Actions.lnk")
link.TargetPath = pythonExe
link.Arguments = """" & scriptDir & "\tools\Arduino_Actions\arduino_actions.py"""
link.WorkingDirectory = scriptDir & "\tools\Arduino_Actions"
link.Description = "MX5-Telemetry Arduino Actions"
link.IconLocation = pythonExe & ",0"
link.Save

' Success message
MsgBox "Shortcuts created successfully on your desktop!" & vbCrLf & vbCrLf & _
       "- LED Simulator.lnk" & vbCrLf & _
       "- Arduino Actions.lnk", vbInformation, "Success"
