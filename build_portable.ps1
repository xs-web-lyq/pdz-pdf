param(
    [string]$OutputRoot = "D:\Downloads\pdz-assistant-1.2\pdz-assistant-1.2\portable_dist"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeSource = Join-Path $repoRoot ".cpython311"
$sitePackagesSource = Join-Path $repoRoot ".standalone-packenv\Lib\site-packages"
$launcherBuild = Join-Path $repoRoot "build\portable-launcher"
$launcherSpec = Join-Path $repoRoot "build\portable-launcher-spec"
$launcherDist = Join-Path $repoRoot "build\portable-launcher-dist"
$launcherExe = Join-Path $launcherDist "pdz-assistant-python.exe"

if (Test-Path $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}
if (Test-Path $launcherBuild) {
    Remove-Item -LiteralPath $launcherBuild -Recurse -Force
}
if (Test-Path $launcherSpec) {
    Remove-Item -LiteralPath $launcherSpec -Recurse -Force
}
if (Test-Path $launcherDist) {
    Remove-Item -LiteralPath $launcherDist -Recurse -Force
}

New-Item -ItemType Directory -Force $OutputRoot | Out-Null

& (Join-Path $repoRoot ".standalone-packenv\Scripts\python.exe") `
    -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "pdz-assistant-python" `
    --icon (Join-Path $PSScriptRoot "Gemini.ico") `
    --distpath $launcherDist `
    --workpath $launcherBuild `
    --specpath $launcherSpec `
    (Join-Path $PSScriptRoot "portable_launcher.py")

Copy-Item -LiteralPath $launcherExe -Destination (Join-Path $OutputRoot "pdz-assistant-python.exe") -Force

$runtimeTarget = Join-Path $OutputRoot "runtime"
Copy-Item -LiteralPath $runtimeSource -Destination $runtimeTarget -Recurse -Force
$sitePackagesTarget = Join-Path $runtimeTarget "Lib\site-packages"
Get-ChildItem -LiteralPath $sitePackagesSource -Force | Copy-Item -Destination $sitePackagesTarget -Recurse -Force

$appTarget = Join-Path $OutputRoot "app"
New-Item -ItemType Directory -Force $appTarget | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "main.py") -Destination (Join-Path $appTarget "main.py") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Gemini.ico") -Destination (Join-Path $appTarget "Gemini.ico") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "pdz_assistant") -Destination (Join-Path $appTarget "pdz_assistant") -Recurse -Force

$readme = @"
This is the portable build of pdz assistant python.

Start the app with:
  pdz-assistant-python.exe

The bundled runtime lives in:
  runtime\

The application code lives in:
  app\
"@
Set-Content -LiteralPath (Join-Path $OutputRoot "README_PORTABLE.txt") -Value $readme -Encoding ascii
