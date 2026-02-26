WScript.Sleep 8000  ' รอ 8 วิ ให้ Google Drive mount ก่อน

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\Users\PanitanNanti\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\pythonw.exe"" ""G:\My Drive\ProjectDev\widget\widget.py""", 0, False
