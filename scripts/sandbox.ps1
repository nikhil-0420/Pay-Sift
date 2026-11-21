# PaySift Sandbox Runner (PowerShell Wrapper)
# Usage:
#   .\scripts\sandbox.ps1 -File <path_to_candidate.py> -Mode <normal|restart|concurrency>
# Example:
#   .\scripts\sandbox.ps1 -File "ref/handler_ref.py" -Mode normal

param(
    [Parameter(Mandatory=$true)]
    [string]$File,

    [Parameter(Mandatory=$false)]
    [string]$Mode = "normal"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot
& "$ProjectRoot\.venv\Scripts\python.exe" -m runner.sandbox --file $File --mode $Mode
exit $LASTEXITCODE
