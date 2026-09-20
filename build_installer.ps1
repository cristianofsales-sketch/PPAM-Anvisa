$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Ambiente isolado ausente. Crie .venv-build e instale requirements-build.lock.txt antes de compilar.'
}
& $python build_desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Build ou testes falharam. Nenhum instalador foi aprovado.' }
