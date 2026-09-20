$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$target = [IO.Path]::GetFullPath($PSScriptRoot)
$manifestPath = Join-Path $target 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.application -ne 'PPAM Anvisa') { throw 'Instalacao nao reconhecida.' }
if ([Windows.Forms.MessageBox]::Show('Remover PPAM? Documentos exportados e arquivos modificados serao preservados.', 'PPAM', 'YesNo') -ne 'Yes') { exit }
$executable = Join-Path $target 'PPAM Anvisa.exe'
$running = Get-CimInstance Win32_Process -Filter "Name = 'PPAM Anvisa.exe'" | Where-Object { $_.ExecutablePath -eq $executable }
if ($running) { [Windows.Forms.MessageBox]::Show('Feche o PPAM antes de desinstalar.', 'PPAM'); exit 1 }
$owned = @()
foreach ($entry in $manifest.files.PSObject.Properties) {
    $path = [IO.Path]::GetFullPath((Join-Path $target $entry.Name))
    if (-not $path.StartsWith($target + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho fora da instalacao.' }
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $entry.Value.sha256) { $owned += $path }
    }
}
# Only individually verified application files; never recursively delete the target.
foreach ($path in $owned) { Remove-Item -LiteralPath $path }
$shell = New-Object -ComObject WScript.Shell
foreach ($location in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    $shortcut = Join-Path $location 'PPAM Anvisa.lnk'
    if ((Test-Path -LiteralPath $shortcut) -and $shell.CreateShortcut($shortcut).TargetPath -eq $executable) { Remove-Item -LiteralPath $shortcut }
}
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PPAM Anvisa'
if ((Get-ItemProperty -LiteralPath $registry -ErrorAction SilentlyContinue).InstallLocation -eq $target) { Remove-Item -LiteralPath $registry }
Remove-Item -LiteralPath $manifestPath
[Windows.Forms.MessageBox]::Show('Arquivos do PPAM removidos. Documentos, arquivos modificados, backups e logs foram preservados.', 'PPAM')
