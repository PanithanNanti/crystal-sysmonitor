' CRYSTAL System Monitor — Windows Startup Launcher
' Waits for system services + Google Drive to be ready before launching

Dim WshShell, pythonw, script, retries, driveReady

pythonw = "C:\Users\PanitanNanti\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\pythonw.exe"
script  = "G:\My Drive\ProjectDev\widget\widget.py"

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Wait for G: drive (Google Drive) to be mounted — retry up to 30x every 2s (60s max)
retries   = 0
driveReady = False

Do While retries < 30
    If fso.DriveExists("G:") And fso.FileExists(script) Then
        driveReady = True
        Exit Do
    End If
    WScript.Sleep 2000
    retries = retries + 1
Loop

' Extra buffer after drive is ready
WScript.Sleep 2000

' Launch widget (0 = hidden window, False = don't wait)
If driveReady Then
    WshShell.Run """" & pythonw & """ """ & script & """", 0, False
End If
