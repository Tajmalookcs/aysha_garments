' Stops the app when it's running with no window.
Option Explicit

Dim service, process, stopped
Set service = GetObject("winmgmts:\\.\root\cimv2")
stopped = 0
For Each process In service.ExecQuery("SELECT * FROM Win32_Process WHERE Name = 'python.exe'")
    If Not IsNull(process.CommandLine) Then
        If InStr(process.CommandLine, "waitress") > 0 And InStr(process.CommandLine, "--listen=127.0.0.1:8000") > 0 Then
            process.Terminate
            stopped = stopped + 1
        End If
    End If
Next

If stopped > 0 Then
    MsgBox "Digital Invoicing has stopped.", vbInformation, "Digital Invoicing"
Else
    MsgBox "Digital Invoicing wasn't running.", vbInformation, "Digital Invoicing"
End If
