[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$FontDirectory
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($FontDirectory)) {
    $FontDirectory = Join-Path $PSScriptRoot 'fonts'
}
$fontDirectoryPath = (Resolve-Path -LiteralPath $FontDirectory).Path
$fontFiles = @(Get-ChildItem -LiteralPath $fontDirectoryPath -Filter 'MonatendardNFM-*.ttf' -File)
if ($fontFiles.Count -eq 0) {
    throw "No Monatendard Nerd Font Mono TTF files were found to install: $fontDirectoryPath"
}

$userFontDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$fontRegistry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
if (-not $WhatIfPreference -and -not ('MonatendardNerdFontApiV2' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MonatendardNerdFontApiV2 {
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

if (-not $WhatIfPreference) {
    # GDI itself holds read locks; restore released references on preflight failure.
    $released = @{}
    try {
        foreach ($font in $fontFiles) {
            $destination = Join-Path $userFontDirectory $font.Name
            if (-not (Test-Path -LiteralPath $destination)) { continue }
            $released[$destination] = 0
            while ([MonatendardNerdFontApiV2]::RemoveFontResourceEx($destination, 0, [IntPtr]::Zero)) {
                $released[$destination]++
            }
            $stream = [System.IO.File]::Open(
                $destination, [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None
            )
            $stream.Dispose()
        }
    } catch {
        foreach ($path in $released.Keys) {
            for ($i = 0; $i -lt $released[$path]; $i++) {
                [void][MonatendardNerdFontApiV2]::AddFontResourceEx($path, 0, [IntPtr]::Zero)
            }
        }
        throw "Cannot update fonts. Close applications using the fonts and retry. $($_.Exception.Message)"
    }
    New-Item -ItemType Directory -Force -Path $userFontDirectory | Out-Null
    if (-not (Test-Path -LiteralPath $fontRegistry)) {
        New-Item -Path $fontRegistry | Out-Null
    }
}

foreach ($font in $fontFiles) {
    $destination = Join-Path $userFontDirectory $font.Name
    $style = [System.IO.Path]::GetFileNameWithoutExtension($font.Name).Substring(
        'MonatendardNFM-'.Length
    )
    $registryName = "Monatendard Nerd Font Mono $style (TrueType)"
    if ($PSCmdlet.ShouldProcess($destination, 'Install Nerd font for the current user')) {
        while (
            (Test-Path -LiteralPath $destination) -and
            [MonatendardNerdFontApiV2]::RemoveFontResourceEx(
                $destination, 0, [IntPtr]::Zero
            )
        ) {}
        try {
            Copy-Item -LiteralPath $font.FullName -Destination $destination -Force
        } catch {
            throw "Cannot update font: $destination. Close applications using the fonts and retry. $($_.Exception.Message)"
        }
        New-ItemProperty `
            -Path $fontRegistry `
            -Name $registryName `
            -Value $destination `
            -PropertyType String `
            -Force | Out-Null
        $loaded = [MonatendardNerdFontApiV2]::AddFontResourceEx(
            $destination, 0, [IntPtr]::Zero
        )
        if ($loaded -eq 0) {
            throw "Failed to load the Nerd font into the current Windows session: $destination. Close applications using the fonts and retry."
        }
    }
}

if (-not $WhatIfPreference) {
    $result = [UIntPtr]::Zero
    [void][MonatendardNerdFontApiV2]::SendMessageTimeout(
        [IntPtr]0xffff, 0x001D, [UIntPtr]::Zero, [IntPtr]::Zero,
        0x0002, 5000, [ref]$result
    )
}

Write-Host "Monatendard Nerd Font Mono: Installed $($fontFiles.Count) font files successfully."
Write-Host 'Please restart your editor and terminal.'
