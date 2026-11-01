Option Explicit
Dim shell, files, root, python, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv\Scripts\pythonw.exe"
If Not files.FileExists(python) Then
  MsgBox "KISS's Python environment is missing. Run scripts\setup_local.py once, then open KISS again.", vbExclamation, "KISS setup"
  WScript.Quit 1
End If
shell.CurrentDirectory = root
command = Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\desktop.py" & Chr(34)
shell.Run command, 0, False
