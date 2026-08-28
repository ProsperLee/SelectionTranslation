#Requires -Version 5.1
param(
    [switch]$Clean,
    [switch]$SkipInstaller,
    [switch]$SkipIcon
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Root ".venv\Scripts\pip.exe"
$ReleaseDir = Join-Path $Root "release"
$AppOut = Join-Path $ReleaseDir "app"
$Spec = Join-Path $PSScriptRoot "SelectionTranslation.spec"
$Iss = Join-Path $PSScriptRoot "installer.iss"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host ("==== {0} ====" -f $Message) -ForegroundColor Cyan
}

function Find-ISCC {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

Push-Location $Root
try {
    if (-not (Test-Path $VenvPython)) {
        throw "venv not found: $VenvPython"
    }

    Write-Step "Install/upgrade pyinstaller"
    & $VenvPip install -U "pyinstaller>=6.3"
    if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

    if ($Clean) {
        Write-Step "Clean old build outputs"
        foreach ($d in @((Join-Path $Root "build"), (Join-Path $Root "dist"), $ReleaseDir)) {
            if (Test-Path $d) {
                Remove-Item $d -Recurse -Force
                Write-Host "Removed $d"
            }
        }
    }

    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    New-Item -ItemType Directory -Force -Path $AppOut | Out-Null

    if (-not $SkipIcon) {
        Write-Step "Generate packaging\app.ico"
        & $VenvPython (Join-Path $PSScriptRoot "make_icon.py")
        if ($LASTEXITCODE -ne 0) { throw "make_icon.py failed" }
    }

    Write-Step "PyInstaller build (logs = progress)"
    $pyinstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
    & $pyinstaller `
        --noconfirm `
        --clean `
        --distpath $AppOut `
        --workpath (Join-Path $Root "build\pyinstaller") `
        $Spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: exit $LASTEXITCODE" }

    $exePath = Join-Path $AppOut "SelectionTranslation\SelectionTranslation.exe"
    if (-not (Test-Path $exePath)) {
        throw "Missing output: $exePath"
    }
    Write-Host "EXE ready: $exePath" -ForegroundColor Green

    # Place high-res ico next to exe for shortcut IconFilename
    $icoSrc = Join-Path $PSScriptRoot "app.ico"
    $icoDst = Join-Path $AppOut "SelectionTranslation\app.ico"
    if (Test-Path $icoSrc) {
        Copy-Item $icoSrc $icoDst -Force
        Write-Host "Copied app.ico beside exe for sharp shortcuts"
    }

    if ($SkipInstaller) {
        Write-Host "Skipped installer (-SkipInstaller)"
        Write-Host ("App folder: {0}" -f (Join-Path $AppOut "SelectionTranslation"))
        return
    }

    Write-Step "Locate Inno Setup ISCC"
    $iscc = Find-ISCC
    if (-not $iscc) {
        Write-Host "Inno Setup 6 not found." -ForegroundColor Yellow
        Write-Host "Install: winget install --id JRSoftware.InnoSetup -e"
        Write-Host "Or download: https://jrsoftware.org/isdl.php"
        Write-Host "You can still run the folder build:"
        Write-Host "  $exePath"
        return
    }

    Write-Host "Using: $iscc"
    Write-Step "Compile installer (ISCC progress below)"
    & $iscc $Iss
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed: exit $LASTEXITCODE" }

    $setup = Get-ChildItem $ReleaseDir -Filter "SelectionTranslation-Setup-*.exe" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($setup) {
        Write-Host ""
        Write-Host ("Setup ready: {0}" -f $setup.FullName) -ForegroundColor Green
    }
    Write-Host "Done." -ForegroundColor Green
}
finally {
    Pop-Location
}
