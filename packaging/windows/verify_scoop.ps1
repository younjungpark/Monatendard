#requires -Version 5.1
<#
Run on a disposable Windows CI account with Scoop and gh already installed.
Uses a non-Git local bucket: Scoop does not accept local paths on every version.
The normal run tests released archives, including the real v0.2.3 -> current
upgrade. -SourceScripts overlays ONLY extracted current install directories,
never release assets or tracked manifests. -TestSourceScripts additionally runs
both ZIP installers/uninstallers repeatedly in this same Windows PowerShell 5.1
process, after Scoop has relinquished ownership of the fonts.
#>
[CmdletBinding()]
param([switch]$SourceScripts, [switch]$TestSourceScripts)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT' -or $PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run this integration test with Windows PowerShell 5.1 (powershell.exe).'
}
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$fontDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$registry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$scoopRoot = if ($env:SCOOP) { $env:SCOOP } else { Join-Path $HOME 'scoop' }
$bucketRoot = Join-Path $scoopRoot 'buckets\monatendard'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('monatendard-ci-' + [guid]::NewGuid().ToString('N'))
$packages = @(
    @{ Name = 'monatendard'; Prefix = 'Monatendard-'; Family = 'Monatendard'; Suffix = ''; Asset = 'Monatendard-v0.2.3-Desktop.zip' },
    @{ Name = 'monatendard-nerd'; Prefix = 'MonatendardNFM-'; Family = 'Monatendard Nerd Font Mono'; Suffix = '-Nerd'; Asset = 'Monatendard-v0.2.3-Desktop-Nerd.zip' }
)

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw "Assertion failed: $Message" }
}
function Invoke-Native([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments | Out-Host
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "$Command $($Arguments -join ' ') failed ($code)" }
}
function Invoke-Scoop([string[]]$Arguments, [switch]$ExpectFailure) {
    # Scoop sometimes throws rather than setting LASTEXITCODE. Capture both;
    # assertions on the files/registry below still prove the intended failure.
    $global:LASTEXITCODE = 0
    $failed = $false
    try {
        & scoop @Arguments | Out-Host
        $failed = ($LASTEXITCODE -ne 0)
    } catch {
        if (-not $ExpectFailure) { throw }
        Write-Host $_
        $failed = $true
    }
    if ($ExpectFailure) {
        Assert-True $failed "scoop $($Arguments -join ' ') must fail"
    } else {
        Assert-True (-not $failed) "scoop $($Arguments -join ' ') must succeed (exit $LASTEXITCODE)"
    }
}
function Get-FontRegistry {
    $values = @{}
    if (Test-Path -LiteralPath $registry) {
        $key = Get-Item -LiteralPath $registry
        foreach ($name in $key.GetValueNames()) { $values[$name] = $key.GetValue($name) }
    }
    return $values
}
function Assert-RegistryEqual($Before, $After) {
    Assert-True ($Before.Count -eq $After.Count) 'registry value count unchanged'
    foreach ($name in $Before.Keys) {
        Assert-True ($After.ContainsKey($name) -and $After[$name] -ceq $Before[$name]) "registry value preserved: $name"
    }
}
function Assert-UnrelatedRegistry {
    $after = Get-FontRegistry
    foreach ($p in $packages) {
        foreach ($name in @($after.Keys)) {
            if ($name -like ($p.Family + ' * (TrueType)')) { $after.Remove($name) }
        }
    }
    Assert-RegistryEqual $script:baseline $after
}
function Get-AppDirectory($Package) {
    return Join-Path $scoopRoot ('apps\' + $Package.Name + '\current')
}
function Assert-Family($Package, [bool]$Installed, [string]$ArchiveFonts) {
    $actual = @(Get-ChildItem -LiteralPath $fontDir -Filter ($Package.Prefix + '*.ttf') -File -ErrorAction SilentlyContinue)
    $expected = @(Get-ChildItem -LiteralPath $ArchiveFonts -Filter ($Package.Prefix + '*.ttf') -File)
    Assert-True ($expected.Count -eq 14) "$($Package.Name) archive has exactly 14 TTFs"
    $values = Get-FontRegistry
    $familyNames = @($values.Keys | Where-Object { $_ -like ($Package.Family + ' * (TrueType)') })
    if (-not $Installed) {
        Assert-True ($actual.Count -eq 0 -and $familyNames.Count -eq 0) "$($Package.Name) completely removed"
        return
    }
    Assert-True ($actual.Count -eq 14 -and $familyNames.Count -eq 14) "$($Package.Name) has 14 files and registrations"
    foreach ($font in $expected) {
        $destination = Join-Path $fontDir $font.Name
        $style = $font.BaseName.Substring($Package.Prefix.Length)
        $name = $Package.Family + ' ' + $style + ' (TrueType)'
        Assert-True ($values.ContainsKey($name) -and $values[$name] -eq $destination) "correct user registry path: $name"
        Assert-True ((Get-FileHash -LiteralPath $destination).Hash -eq (Get-FileHash -LiteralPath $font.FullName).Hash) "installed TTF matches archive: $($font.Name)"
    }
}
function Set-LocalManifest($Package, $Manifest, [switch]$Overlay) {
    # Operates exclusively on the disposable local bucket, not repoRoot/bucket.
    # Never mutate Package.Current: historical manifests must keep old ZIP scripts.
    $Manifest = $Manifest | ConvertTo-Json -Depth 20 | ConvertFrom-Json
    if ($Overlay) {
        $source = $PSScriptRoot.Replace("'", "''")
        $overlayLines = @(
            "Copy-Item -LiteralPath '$source\Install-Monatendard$($Package.Suffix).ps1' -Destination `"`$dir\Install-Monatendard$($Package.Suffix).ps1`" -Force",
            "Copy-Item -LiteralPath '$source\Uninstall-Monatendard$($Package.Suffix).ps1' -Destination `"`$dir\Uninstall-Monatendard$($Package.Suffix).ps1`" -Force"
        )
        $Manifest.pre_install = @($Manifest.pre_install) + $overlayLines
    }
    $Manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $bucketRoot ('bucket\' + $Package.Name + '.json')) -Encoding UTF8
}

Get-Command scoop, gh -ErrorAction Stop | Out-Null
Assert-True (-not (Test-Path -LiteralPath $bucketRoot)) 'a pre-existing monatendard bucket must not be replaced'
# Fail before acquiring ownership: never remove a developer\'s existing fonts.
foreach ($p in $packages) {
    Assert-True (-not (Test-Path (Join-Path $scoopRoot ('apps\' + $p.Name)))) "no existing Scoop installation of $($p.Name)"
    Assert-True (@(Get-ChildItem -Path (Join-Path $fontDir ($p.Prefix + '*.ttf')) -ErrorAction SilentlyContinue).Count -eq 0) "no existing manual fonts for $($p.Name)"
}
$baseline = Get-FontRegistry
foreach ($name in $baseline.Keys) {
    Assert-True ($name -notlike 'Monatendard * (TrueType)') 'no existing Monatendard font registration'
}
$manualFile = $null
$lock = $null
$owned = $false
try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $bucketRoot 'bucket') -Force | Out-Null
    $owned = $true
    New-Item -ItemType Directory -Path $fontDir -Force | Out-Null
    foreach ($p in $packages) {
        $p.Current = Get-Content -Raw -LiteralPath (Join-Path $repoRoot ('bucket\' + $p.Name + '.json')) | ConvertFrom-Json
        $p.Fonts = Join-Path $tempRoot ($p.Name + '-fonts')
        Set-LocalManifest $p $p.Current -Overlay:$SourceScripts
    }

    Write-Host 'TEST: both current official packages coexist; actual files and HKCU registrations'
    foreach ($p in $packages) {
        Invoke-Scoop @('install', ('monatendard/' + $p.Name))
        Copy-Item -LiteralPath (Join-Path (Get-AppDirectory $p) 'fonts') -Destination $p.Fonts -Recurse
        Assert-Family $p $true $p.Fonts
    }
    Assert-UnrelatedRegistry
    Invoke-Scoop @('uninstall', $packages[0].Name)
    Assert-Family $packages[0] $false $packages[0].Fonts
    Assert-Family $packages[1] $true $packages[1].Fonts
    Invoke-Scoop @('install', ('monatendard/' + $packages[0].Name))
    Invoke-Scoop @('uninstall', $packages[1].Name)
    Assert-Family $packages[0] $true $packages[0].Fonts
    Assert-Family $packages[1] $false $packages[1].Fonts
    Invoke-Scoop @('install', ('monatendard/' + $packages[1].Name))

    foreach ($p in $packages) {
        Write-Host "TEST: locked final font blocks uninstall without any partial mutation: $($p.Name)"
        $fonts = @(Get-ChildItem -LiteralPath $p.Fonts -Filter ($p.Prefix + '*.ttf') | Sort-Object Name)
        $before = Get-FontRegistry
        $lock = [IO.File]::Open((Join-Path $fontDir $fonts[-1].Name), 'Open', 'Read', 'Read')
        try {
            Invoke-Scoop @('uninstall', $p.Name) -ExpectFailure
            Assert-RegistryEqual $before (Get-FontRegistry)
            Assert-Family $p $true $p.Fonts
            Assert-True (Test-Path (Get-AppDirectory $p)) 'failed uninstall retains app'
        } finally { $lock.Dispose(); $lock = $null }
        Invoke-Scoop @('uninstall', $p.Name)
        Assert-Family $p $false $p.Fonts

        Write-Host "TEST: manual same-family font blocks Scoop before overwriting: $($p.Name)"
        $manualFile = Join-Path $fontDir $fonts[0].Name
        Copy-Item -LiteralPath $fonts[0].FullName -Destination $manualFile
        $before = Get-FontRegistry
        Invoke-Scoop @('install', ('monatendard/' + $p.Name)) -ExpectFailure
        Assert-RegistryEqual $before (Get-FontRegistry)
        Assert-True ((Get-FileHash $manualFile).Hash -eq (Get-FileHash $fonts[0].FullName).Hash) 'manual file unchanged'
        Assert-True (@(Get-ChildItem -LiteralPath $fontDir -Filter ($p.Prefix + '*.ttf')).Count -eq 1) 'no additional fonts installed on rejection'
        Remove-Item -LiteralPath $manualFile -Force
        $manualFile = $null
        # Scoop can retain a failed extraction. Remove it via the real CLI.
        if (Test-Path (Join-Path $scoopRoot ('apps\' + $p.Name))) { Invoke-Scoop @('uninstall', $p.Name) }
    }
    Assert-UnrelatedRegistry

    Write-Host 'TEST: real official v0.2.3 -> current Scoop upgrade (not a synthetic version)'
    Invoke-Native gh @('release', 'download', 'v0.2.3', '--repo', 'younjungpark/Monatendard', '--pattern', '*Desktop*.zip', '--pattern', 'SHA256SUMS.txt', '--dir', $tempRoot)
    $checksums = Get-Content -LiteralPath (Join-Path $tempRoot 'SHA256SUMS.txt')
    foreach ($p in $packages) {
        $line = @($checksums | Where-Object { $_ -match ('^[0-9a-fA-F]{64}\s+\*?' + [regex]::Escape($p.Asset) + '$') })
        Assert-True ($line.Count -eq 1) "published checksum exists for $($p.Asset)"
        $hash = ($line[0] -split '\s+')[0]
        Assert-True ((Get-FileHash -LiteralPath (Join-Path $tempRoot $p.Asset) -Algorithm SHA256).Hash -eq $hash) 'download matches official SHA256SUMS'
        $prior = $p.Current | ConvertTo-Json -Depth 20 | ConvertFrom-Json
        $prior.version = '0.2.3'
        $prior.url = 'https://github.com/younjungpark/Monatendard/releases/download/v0.2.3/' + $p.Asset
        $prior.hash = $hash
        # Keep the real old ZIP scripts: subprocess hooks isolate their Add-Type.
        Set-LocalManifest $p $prior
        Invoke-Scoop @('install', ('monatendard/' + $p.Name))
        $oldFonts = Join-Path $tempRoot ($p.Name + '-old-fonts')
        Copy-Item -LiteralPath (Join-Path (Get-AppDirectory $p) 'fonts') -Destination $oldFonts -Recurse
        Assert-Family $p $true $oldFonts
        Set-LocalManifest $p ($p.Current | ConvertTo-Json -Depth 20 | ConvertFrom-Json) -Overlay:$SourceScripts
    }
    foreach ($p in $packages) {
        Invoke-Scoop @('update', $p.Name)
        $installed = Get-Content -Raw -LiteralPath (Join-Path (Get-AppDirectory $p) 'manifest.json') | ConvertFrom-Json
        Assert-True ($installed.version -eq $p.Current.version) 'Scoop installed the current version after update'
        Assert-Family $p $true $p.Fonts
    }
    foreach ($p in $packages) { Invoke-Scoop @('uninstall', $p.Name); Assert-Family $p $false $p.Fonts }
    Assert-UnrelatedRegistry

    if ($TestSourceScripts) {
        Write-Host 'TEST: checked-out ZIP scripts repeated in ONE Windows PowerShell 5.1 process'
        # Source font copies survive Scoop uninstall, with no remaining Scoop ownership.
        # Using & in THIS process deliberately exposes incompatible Add-Type reuse.
        for ($cycle = 0; $cycle -lt 2; $cycle++) {
            foreach ($p in $packages) {
                & (Join-Path $PSScriptRoot ('Install-Monatendard' + $p.Suffix + '.ps1')) -FontDirectory $p.Fonts
                Assert-Family $p $true $p.Fonts
                # Reinstall in the same session, exercising resource unloading.
                & (Join-Path $PSScriptRoot ('Install-Monatendard' + $p.Suffix + '.ps1')) -FontDirectory $p.Fonts
                Assert-Family $p $true $p.Fonts
            }
            foreach ($p in $packages) {
                $before = Get-FontRegistry
                $last = @(Get-ChildItem -LiteralPath $p.Fonts -Filter ($p.Prefix + '*.ttf') | Sort-Object Name)[-1]
                $lock = [IO.File]::Open((Join-Path $fontDir $last.Name), 'Open', 'Read', 'Read')
                try {
                    $rejected = $false
                    try { & (Join-Path $PSScriptRoot ('Install-Monatendard' + $p.Suffix + '.ps1')) -FontDirectory $p.Fonts } catch { $rejected = $true }
                    Assert-True $rejected 'source reinstall rejects a locked final font'
                    Assert-RegistryEqual $before (Get-FontRegistry)
                    Assert-Family $p $true $p.Fonts
                    $rejected = $false
                    try { & (Join-Path $PSScriptRoot ('Uninstall-Monatendard' + $p.Suffix + '.ps1')) } catch { $rejected = $true }
                    Assert-True $rejected 'source uninstall rejects a locked final font'
                    Assert-RegistryEqual $before (Get-FontRegistry)
                    Assert-Family $p $true $p.Fonts
                } finally { $lock.Dispose(); $lock = $null }
            }
            & (Join-Path $PSScriptRoot 'Uninstall-Monatendard.ps1')
            Assert-Family $packages[0] $false $packages[0].Fonts
            Assert-Family $packages[1] $true $packages[1].Fonts
            & (Join-Path $PSScriptRoot 'Uninstall-Monatendard-Nerd.ps1')
            Assert-Family $packages[1] $false $packages[1].Fonts
            Assert-UnrelatedRegistry
        }
    }
    Assert-RegistryEqual $baseline (Get-FontRegistry)
    Write-Host 'PASS: Scoop integration verification completed.'
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    if ($null -ne $manualFile -and (Test-Path -LiteralPath $manualFile)) { Remove-Item -LiteralPath $manualFile -Force }
    if ($owned) {
        foreach ($p in $packages) {
            # Cleanup is best effort on failure; the assertions above are authoritative.
            try {
                if (Test-Path (Join-Path $scoopRoot ('apps\' + $p.Name))) { Invoke-Scoop @('uninstall', $p.Name) }
                & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot ('Uninstall-Monatendard' + $p.Suffix + '.ps1')) | Out-Host
                if ($LASTEXITCODE -ne 0) { Write-Warning "Source cleanup failed for $($p.Name) (exit $LASTEXITCODE)" }
            } catch { Write-Warning "Cleanup failed for $($p.Name): $_" }
        }
        Remove-Item -LiteralPath $bucketRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
