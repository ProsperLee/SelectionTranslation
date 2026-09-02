#Requires -Version 5.1
<#
.SYNOPSIS
  克隆 drawnix 上游并构建 web 前端（供 SelectionTranslation 托盘「思维导图」嵌入）。

.DESCRIPTION
  1. 若 web/drawnix 尚无 package.json，则从 GitHub 浅克隆 develop 分支
  2. 为 vite 设置 base: './'（Qt file:// 加载）
  3. npm install && npm run build:web
#>
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$DrawnixDir = $PSScriptRoot
$PackageJson = Join-Path $DrawnixDir "package.json"
$ViteConfig = Join-Path $DrawnixDir "apps\web\vite.config.ts"
$IndexHtml = Join-Path $DrawnixDir "dist\apps\web\index.html"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host ("==== {0} ====" -f $Message) -ForegroundColor Cyan
}

function Ensure-ViteRelativeBase {
    if (-not (Test-Path $ViteConfig)) {
        throw "Missing vite config: $ViteConfig"
    }
    $text = Get-Content $ViteConfig -Raw
    if ($text -match "base\s*:\s*['\`"]\./['\`"]") {
        Write-Host "vite base already relative" -ForegroundColor DarkGray
        return
    }
    if ($text -match "export default defineConfig\(\{") {
        $patched = $text -replace "export default defineConfig\(\{", "export default defineConfig({`n  base: './',"
        Set-Content -Path $ViteConfig -Value $patched -Encoding UTF8 -NoNewline
        Write-Host "Patched vite.config.ts: base './'" -ForegroundColor Green
        return
    }
    throw "Cannot patch vite.config.ts — unexpected format"
}

if (-not (Test-Path $PackageJson)) {
    Write-Step "Clone plait-board/drawnix (develop)"
    $parent = Split-Path $DrawnixDir -Parent
    $tmp = Join-Path $parent "_drawnix_clone_tmp"
    if (Test-Path $tmp) {
        Remove-Item $tmp -Recurse -Force
    }
    git clone --depth 1 --branch develop https://github.com/plait-board/drawnix.git $tmp
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
    Get-ChildItem $tmp | Copy-Item -Destination $DrawnixDir -Recurse -Force
    Remove-Item $tmp -Recurse -Force
}

Ensure-ViteRelativeBase

if ($SkipBuild) {
    Write-Host "Skipped build (-SkipBuild)"
    return
}

Write-Step "npm install (drawnix)"
Push-Location $DrawnixDir
try {
    if (-not (Test-Path (Join-Path $DrawnixDir "node_modules"))) {
        & npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    Write-Step "npm run build:web"
    & npm run build:web
    if ($LASTEXITCODE -ne 0) { throw "npm run build:web failed" }
}
finally {
    Pop-Location
}

if (-not (Test-Path $IndexHtml)) {
    throw "Build missing: $IndexHtml"
}
Write-Host "Drawnix ready: $IndexHtml" -ForegroundColor Green
