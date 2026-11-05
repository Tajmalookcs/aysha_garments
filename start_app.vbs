' Opens the app with no black window. The first run uses start.bat, so the install progress shows.
Option Explicit

Const APP_URL = "http://127.0.0.1:8000"
Const WAIT_SECONDS = 45

Dim shell, fso, folder, python
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
python = "venv\Scripts\python.exe"

Function AppIsRunning()
    Dim http
    AppIsRunning = False
    On Error Resume Next
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 1000, 1000, 2000, 2000
    http.open "GET", APP_URL, False
    http.send
    If Err.Number = 0 Then
        If http.status > 0 Then AppIsRunning = True
    End If
    On Error GoTo 0
End Function

Function RunHidden(command)
    RunHidden = shell.Run("cmd /c " & command & " >> instance\app.log 2>&1", 0, True)
End Function

Sub AddShortcut(name, target)
    Dim path, link
    path = shell.SpecialFolders("Desktop") & "\" & name & ".lnk"
    If fso.FileExists(path) Then Exit Sub
    Set link = shell.CreateShortcut(path)
    link.TargetPath = fso.BuildPath(folder, target)
    link.WorkingDirectory = folder
    link.Save
End Sub

Sub Fail(message)
    MsgBox message & vbCrLf & vbCrLf & "Details are in " & fso.BuildPath(folder, "instance\app.log"), vbExclamation, "Digital Invoicing"
    WScript.Quit 1
End Sub

If AppIsRunning() Then
    shell.Run APP_URL
    WScript.Quit 0
End If

AddShortcut "Digital Invoicing", "start_app.vbs"
AddShortcut "Stop Digital Invoicing", "stop_app.vbs"

If Not fso.FolderExists("instance") Then fso.CreateFolder "instance"

Dim ready
ready = False
If fso.FileExists(python) Then
    ready = (RunHidden(python & " -c ""import django, whitenoise, waitress, requests, cryptography, qrcode""") = 0)
End If
If Not ready Then
    shell.Run "start.bat", 1, False
    WScript.Quit 0
End If

If RunHidden(python & " manage.py migrate --noinput") <> 0 Then Fail "The app could not update its database."
If RunHidden(python & " manage.py collectstatic --noinput") <> 0 Then Fail "The app could not prepare its files."

shell.Run "cmd /c " & python & " -m waitress --listen=127.0.0.1:8000 config.wsgi:application >> instance\app.log 2>&1", 0, False

Dim waited
For waited = 1 To WAIT_SECONDS
    If AppIsRunning() Then
        shell.Run APP_URL
        WScript.Quit 0
    End If
    WScript.Sleep 1000
Next
Fail "The app did not start."
