# Zkompiluje modul IIS RemoteUserModule do složky bin\ aplikace (kompilátor je součástí .NET Framework na serveru).
# Použití (PowerShell jako správce, ve složce aplikace):  .\iis\build-module.ps1
param(
    [string]$AppDir = (Split-Path -Parent $PSScriptRoot)
)

$csc = Join-Path $env:windir 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw "Nenalezen kompilátor: $csc (je potřeba .NET Framework 4.x)" }

$source = Join-Path $PSScriptRoot 'RemoteUserModule.cs'
$bin = Join-Path $AppDir 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
$dll = Join-Path $bin 'RemoteUserModule.dll'

& $csc /nologo /target:library "/out:$dll" /reference:System.Web.dll $source
if ($LASTEXITCODE -ne 0) { throw 'Kompilace selhala.' }
Write-Host "OK: $dll"
