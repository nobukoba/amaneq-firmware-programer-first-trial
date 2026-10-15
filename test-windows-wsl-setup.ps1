# Offline control-flow checks: no real installation, USB transfer or WSL calls.
$ErrorActionPreference = 'Stop'
$source = Get-Content -Raw (Join-Path $PSScriptRoot 'setup-windows-wsl.ps1')
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$stubs = @{
    'Require-Administrator' = 'function Require-Administrator {}'
    'Require-Wsl2' = 'function Require-Wsl2 {}'
    'Find-Usbipd' = 'function Find-Usbipd { return "mock-usbipd" }'
    'Invoke-Checked' = 'function Invoke-Checked { param($File, $Arguments) $script:Calls.Add(@{File=$File; Arguments=$Arguments}) }'
    'Invoke-WslScript' = 'function Invoke-WslScript { param($Script, [switch]$Root) $script:Calls.Add(@{File="mock-wsl-script"; Arguments=@($Script)}) }'
}
$functions = $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $true)
foreach ($node in ($functions | Sort-Object { $_.Extent.StartOffset } -Descending)) {
    if ($stubs.ContainsKey($node.Name)) {
        $source = $source.Remove($node.Extent.StartOffset, $node.Extent.EndOffset - $node.Extent.StartOffset).Insert($node.Extent.StartOffset, $stubs[$node.Name])
    }
}
$source = $source.Replace('exit 1', 'throw')
$program = [scriptblock]::Create($source)
foreach ($action in @('List', 'Attach', 'Detach')) {
    $script:Calls = New-Object 'System.Collections.Generic.List[object]'
    & $program -Action $action -BusId '4-4'
    $usbCalls = @($script:Calls | Where-Object File -eq 'mock-usbipd')
    $actual = @($usbCalls | ForEach-Object { $_.Arguments -join ' ' }) -join ';'
    $expected = switch ($action) {
        'List' { 'list' }
        'Attach' { 'bind --busid 4-4;attach --wsl --busid 4-4;list' }
        'Detach' { 'detach --busid 4-4;list' }
    }
    if ($actual -ne $expected) { throw "Unexpected $action commands: $actual" }
}
$script:Calls.Clear()
try { & $program -Action Attach; throw 'Missing BUSID was accepted.' }
catch { if ($_.Exception.Message -notmatch 'Supply -BusId') { throw } }
if ($script:Calls.Count) { throw 'Missing BUSID caused external calls.' }
Write-Host 'WSL setup parser and offline USB action checks passed.'
