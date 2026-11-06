' ProjectSeal — запуск без консольного окна.
' Двойной клик по этому файлу запускает ProjectSeal.exe, если он рядом,
' иначе пытается найти локальное окружение Python.
Option Explicit

Dim fso, shell, base, exePath, pywPath, pythonwPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = base & "\ProjectSeal.exe"
pywPath = base & "\run_projectseal.pyw"
pythonwPath = base & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(exePath) Then
  shell.Run """" & exePath & """", 1, False
  WScript.Quit 0
End If

If fso.FileExists(pythonwPath) And fso.FileExists(pywPath) Then
  shell.Run """" & pythonwPath & """ """ & pywPath & """", 0, False
  WScript.Quit 0
End If

On Error Resume Next
shell.Run "pythonw.exe """ & pywPath & """", 0, False
If Err.Number = 0 Then
  WScript.Quit 0
End If
On Error GoTo 0

MsgBox "Не найден ProjectSeal.exe.", 16, "ProjectSeal"
