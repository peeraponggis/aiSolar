$ws = New-Object -ComObject WScript.Shell
$desktop = $ws.SpecialFolders("Desktop")
$s = $ws.CreateShortcut("$desktop\LungPee Agent.lnk")
$s.TargetPath = "C:\Users\Lenovo\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
$s.Arguments = '"F:\LocalAI\lungpee-agent\agent.py"'
$s.WorkingDirectory = "F:\LocalAI\lungpee-agent"
$s.Description = "LungPee AI Agent"
$s.Save()
Write-Host "Shortcut created at: $desktop\LungPee Agent.lnk"
