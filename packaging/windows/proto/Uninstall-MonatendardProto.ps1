[CmdletBinding(SupportsShouldProcess)]
param(
    # e.g. MonatendardProtoANFM
    [Parameter(Mandatory)]
    [string]$FilePrefix
)

$ErrorActionPreference = 'Stop'
$userFontDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$fontRegistry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'

if (-not $WhatIfPreference) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MonatendardProtoUninstallApi {
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool RemoveFontResourceEx(string fileName, uint flags, IntPtr reserved);
}
'@
}

$removed = 0
if (Test-Path -LiteralPath $fontRegistry) {
    $properties = (Get-ItemProperty -LiteralPath $fontRegistry).PSObject.Properties |
        Where-Object { $_.Value -is [string] }
    foreach ($property in $properties) {
        $fileName = [System.IO.Path]::GetFileName([string]$property.Value)
        if ($fileName -notlike "$FilePrefix-*.ttf") {
            continue
        }
        $path = Join-Path $userFontDirectory $fileName
        if ($PSCmdlet.ShouldProcess($path, 'Remove prototype font for the current user')) {
            while (
                (Test-Path -LiteralPath $path) -and
                [MonatendardProtoUninstallApi]::RemoveFontResourceEx($path, 0, [IntPtr]::Zero)
            ) {}
            Remove-ItemProperty -LiteralPath $fontRegistry -Name $property.Name
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            $removed++
        }
    }
}

Write-Host "${FilePrefix}: Removed $removed font files."
