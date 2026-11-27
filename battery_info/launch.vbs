' ============================================================
' Battery Monitor Launcher
' F:\LocalAI\battery_info\launch.vbs
' Double-click to start server + open Battery Dashboard
' ============================================================
Option Explicit

Dim WshShell, fso, ScriptDir, serverScript, url, edgePath

Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

ScriptDir    = fso.GetParentFolderName(WScript.ScriptFullName)
serverScript = ScriptDir & "\server.ps1"
url          = "http://localhost:8765/"

' --- Start server (hidden) ---
WshShell.Run "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -NonInteractive -File """ & serverScript & """", 0, False

WScript.Sleep 2500

' --- Open dashboard in Edge App mode ---
edgePath = WshShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe"
If Not fso.FileExists(edgePath) Then
    edgePath = WshShell.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe"
End If

If fso.FileExists(edgePath) Then
    WshShell.Run """" & edgePath & """ --app=" & url & " --window-size=1000,700", 1, False
Else
    WshShell.Run "rundll32 url.dll,FileProtocolHandler " & url, 1, False
End If

Set fso      = Nothing
Set WshShell = Nothing
