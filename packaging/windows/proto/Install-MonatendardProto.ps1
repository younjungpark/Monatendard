[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [string]$FontDirectory,

    # e.g. MonatendardProtoANFM
    [Parameter(Mandatory)]
    [string]$FilePrefix,

    # e.g. Monatendard Proto A Nerd Font Mono
    [Parameter(Mandatory)]
    [string]$FamilyName
)

$ErrorActionPreference = 'Stop'
$fontDirectoryPath = (Resolve-Path -LiteralPath $FontDirectory).Path
$fontFiles = @(Get-ChildItem -LiteralPath $fontDirectoryPath -Filter "$FilePrefix-*.ttf" -File)
if ($fontFiles.Count -eq 0) {
    throw "No $FamilyName TTF files were found to install: $fontDirectoryPath"
}

$userFontDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$fontRegistry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
New-Item -ItemType Directory -Force -Path $userFontDirectory | Out-Null
if (-not (Test-Path -LiteralPath $fontRegistry)) {
    New-Item -Path $fontRegistry | Out-Null
}

if (-not $WhatIfPreference) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MonatendardProtoFontApi {
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int AddFontResourceEx(string fileName, uint flags, IntPtr reserved);

    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool RemoveFontResourceEx(string fileName, uint flags, IntPtr reserved);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd, uint Msg, UIntPtr wParam, IntPtr lParam,
        uint flags, uint timeout, out UIntPtr result);
}
'@
}

foreach ($font in $fontFiles) {
    $destination = Join-Path $userFontDirectory $font.Name
    $style = [System.IO.Path]::GetFileNameWithoutExtension($font.Name).Substring(
        "$FilePrefix-".Length
    )
    $registryName = "$FamilyName $style (TrueType)"
    if ($PSCmdlet.ShouldProcess($destination, 'Install prototype font for the current user')) {
        while (
            (Test-Path -LiteralPath $destination) -and
            [MonatendardProtoFontApi]::RemoveFontResourceEx(
                $destination, 0, [IntPtr]::Zero
            )
        ) {}
        Copy-Item -LiteralPath $font.FullName -Destination $destination -Force
        New-ItemProperty `
            -Path $fontRegistry `
            -Name $registryName `
            -Value $destination `
            -PropertyType String `
            -Force | Out-Null
        $loaded = [MonatendardProtoFontApi]::AddFontResourceEx(
            $destination, 0, [IntPtr]::Zero
        )
        if ($loaded -eq 0) {
            throw "Failed to load the font into the current Windows session: $destination"
        }
    }
}

if (-not $WhatIfPreference) {
    $result = [UIntPtr]::Zero
    [void][MonatendardProtoFontApi]::SendMessageTimeout(
        [IntPtr]0xffff, 0x001D, [UIntPtr]::Zero, [IntPtr]::Zero,
        0x0002, 5000, [ref]$result
    )
}

Write-Host "${FamilyName}: Installed $($fontFiles.Count) font files."
