<#
.SYNOPSIS
Prepare Windows/Ubuntu WSL2 for AMANEQ firmware programming.
.DESCRIPTION
Setup installs usbipd-win and Ubuntu packages, then clones the tool in the
WSL user's home. It never flashes firmware or automatically selects a USB device.
.PARAMETER Action
Setup (default), List, Attach or Detach.
.PARAMETER Distribution
Existing WSL2 distribution name. Default: Ubuntu. Setup uses apt-get.
.PARAMETER BusId
Explicit USB BUSID from List. Required for Attach and Detach.
.EXAMPLE
.\setup-windows-wsl.ps1 -Action Setup
.EXAMPLE
.\setup-windows-wsl.ps1 -Action Attach -BusId 4-4
#>
[CmdletBinding()]
param(
    [ValidateSet('Setup', 'List', 'Attach', 'Detach')]
    [string]$Action = 'Setup',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]*$')]
    [string]$Distribution = 'Ubuntu',
    [ValidatePattern('^[0-9]+-[0-9]+(\.[0-9]+)*$')]
    [string]$BusId
)
$ErrorActionPreference = 'Stop'
function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$File failed (exit $LASTEXITCODE). Resolve the error above and rerun."
    }
}
function Invoke-WslScript {
    param([string]$Script, [switch]$Root)
    $arguments = @('-d', $Distribution)
    if ($Root) { $arguments += @('-u', 'root') }
    # Pipe Bash source over stdin to preserve quoting in Windows PowerShell 5.1.
    # Windows adds CRLF after pipeline strings; keep it inside a trailing Bash comment.
    ($Script.Replace("`r", '') + "`n# End of WSL setup input.") | & wsl.exe @arguments -- bash -s
    if ($LASTEXITCODE -ne 0) { throw "WSL script failed (exit $LASTEXITCODE). Resolve the error above and rerun." }
}
function Require-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run Setup and Attach in an Administrator PowerShell (USB binding needs elevation).'
    }
}
function Find-Usbipd {
    $command = Get-Command usbipd.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $installed = Join-Path $env:ProgramFiles 'usbipd-win\usbipd.exe'
    if (Test-Path -LiteralPath $installed) { return $installed }
    return $null
}
function Require-Wsl2 {
    # Start the requested distribution, then distinguish WSL2 from WSL1.
    Invoke-Checked 'wsl.exe' @('-d', $Distribution, '--', 'sh', '-c',
        'uname -r | grep -qi microsoft-standard-WSL2')
}
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Run this script in Windows PowerShell.' }
    if ($Action -in @('Attach', 'Detach') -and -not $BusId) {
        throw 'Supply -BusId using the exact BUSID printed by -Action List. No device is selected automatically.'
    }
    if ($Action -eq 'Setup') {
        Require-Administrator
        if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
            throw 'Install WSL2/Ubuntu with wsl --install -d Ubuntu, reboot if requested, initialize Ubuntu, then rerun.'
        }
        Write-Host 'Checking the existing WSL2 distribution. If missing, run wsl --install -d Ubuntu and initialize it first.'
        Require-Wsl2
        if (-not (Find-Usbipd)) {
            if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
                throw 'winget is missing. Install usbipd-win from https://github.com/dorssel/usbipd-win/releases and rerun.'
            }
            # Interactive installer lets the user handle any required restart.
            Invoke-Checked 'winget.exe' @('install', '--interactive', '--exact',
                '--id', 'dorssel.usbipd-win', '--source', 'winget',
                '--accept-package-agreements', '--accept-source-agreements')
        }
        if (-not (Find-Usbipd)) { throw 'usbipd-win is unavailable. Complete installation/reboot and rerun.' }
        Invoke-WslScript -Root -Script 'set -e; apt-get update; apt-get install -y git python3 openfpgaloader usbutils; udevadm control --reload-rules'
        $linuxUser = (& wsl.exe -d $Distribution -- id -un | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $linuxUser -notmatch '^[a-z_][a-z0-9_-]*[$]?$') {
            throw 'Cannot determine the default Linux user.'
        }
        Invoke-Checked 'wsl.exe' @('-d', $Distribution, '-u', 'root', '--', 'usermod', '-aG', 'plugdev', $linuxUser)
        # Fixed shell text: no PowerShell/user input is interpolated into Bash.
        $linuxSetup = 'set -e; cd "$HOME"; if [ ! -e amaneq-firmware-programer-first-trial ]; then git clone https://github.com/nobukoba/amaneq-firmware-programer-first-trial.git; fi; cd amaneq-firmware-programer-first-trial; test -f amaneq-firmware-programer.py; python3 amaneq-firmware-programer.py --help'
        Invoke-WslScript -Script $linuxSetup
        Write-Host 'Setup complete. Open a new WSL terminal for plugdev group membership. Existing checkouts were not updated. Keep a WSL terminal open, run List, then Attach with an explicit BUSID.'
    }
    $usbipd = Find-Usbipd
    if (-not $usbipd) { throw 'usbipd-win is missing. Run -Action Setup first.' }
    switch ($Action) {
        'Attach' {
            Require-Administrator
            Require-Wsl2
            Write-Host 'Keep a WSL terminal open. The selected cable will be unavailable to Windows until detached.'
            Invoke-Checked $usbipd @('bind', '--busid', $BusId)
            Invoke-Checked $usbipd @('attach', '--wsl', '--busid', $BusId)
            Invoke-WslScript -Script 'set -e; lsusb; cd "$HOME/amaneq-firmware-programer-first-trial"; python3 amaneq-firmware-programer.py scan'
        }
        'Detach' { Invoke-Checked $usbipd @('detach', '--busid', $BusId) }
    }
    Invoke-Checked $usbipd @('list')
} catch {
    [Console]::Error.WriteLine('ERROR: ' + $_.Exception.Message)
    exit 1
}
