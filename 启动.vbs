' ChaitaAssistant launcher. Double-click to start.
Option Explicit

Dim fso, shell, pyw, script, root
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

pyw = shell.ExpandEnvironmentStrings("%USERPROFILE%") + "\.conda\envs\chaita\pythonw.exe"
root = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(root, "run.py")

If Not fso.FileExists(pyw) Then
    MsgBox "Python not found:" + vbCrLf + pyw + vbCrLf + vbCrLf + "Create the conda env 'chaita' first.", 16, "ChaitaAssistant"
    WScript.Quit 1
End If

If Not fso.FileExists(script) Then
    MsgBox "Entry script not found:" + vbCrLf + script, 16, "ChaitaAssistant"
    WScript.Quit 1
End If

shell.CurrentDirectory = root
shell.Run """" + pyw + """ """ + script + """", 0, False
