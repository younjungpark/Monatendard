[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'
$userFontDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$fontRegistry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$removed = 0

$fontFiles = @()
if (Test-Path -LiteralPath $userFontDirectory) {
    $fontFiles = @(Get-ChildItem -LiteralPath $userFontDirectory -Filter 'Monatendard-*.ttf' -File)
}
if (-not $WhatIfPreference -and -not ('MonatendardFontApiV2' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MonatendardFontApiV2 {
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
    $released = @{}
    try {
        foreach ($font in $fontFiles) {
            $destination = $font.FullName
            $released[$destination] = 0
            while ([MonatendardFontApiV2]::RemoveFontResourceEx($destination, 0, [IntPtr]::Zero)) {
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
                [void][MonatendardFontApiV2]::AddFontResourceEx($path, 0, [IntPtr]::Zero)
            }
        }
        throw "Cannot remove fonts. Close applications using the fonts and retry. $($_.Exception.Message)"
    }
}

foreach ($font in $fontFiles) {
    if ($PSCmdlet.ShouldProcess($font.FullName, 'Remove current-user font file')) {
        while ([MonatendardFontApiV2]::RemoveFontResourceEx(
            $font.FullName, 0, [IntPtr]::Zero
        )) {}
        try {
            Remove-Item -LiteralPath $font.FullName -Force
        } catch {
            throw "Cannot remove font: $($font.FullName). Close applications using the fonts and retry. $($_.Exception.Message)"
        }
        $removed++
    }
}

# Only remove matching registrations after every file deletion has succeeded.
if (Test-Path -LiteralPath $fontRegistry) {
    $properties = (Get-ItemProperty -LiteralPath $fontRegistry).PSObject.Properties
    foreach ($property in $properties) {
        $fileName = [System.IO.Path]::GetFileName([string]$property.Value)
        if ($property.Name -like 'PS*' -or $fileName -notlike 'Monatendard-*.ttf') {
            continue
        }
        $destination = Join-Path $userFontDirectory $fileName
        if ([string]$property.Value -ne $fileName -and [string]$property.Value -ne $destination) {
            continue
        }
        if (($WhatIfPreference -or -not (Test-Path -LiteralPath $destination)) -and
            $PSCmdlet.ShouldProcess($property.Name, 'Remove current-user font registry entry')) {
            Remove-ItemProperty -LiteralPath $fontRegistry -Name $property.Name
        }
    }
}

if (-not $WhatIfPreference) {
    $result = [UIntPtr]::Zero
    [void][MonatendardFontApiV2]::SendMessageTimeout(
        [IntPtr]0xffff, 0x001D, [UIntPtr]::Zero, [IntPtr]::Zero,
        0x0002, 5000, [ref]$result
    )
}

Write-Host "Monatendard: Uninstallation completed. Removed font files: $removed"
Write-Host 'Please restart your editor and terminal.'
