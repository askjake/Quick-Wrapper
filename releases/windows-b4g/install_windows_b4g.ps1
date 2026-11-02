# Frozen B4g engineering evaluation installer, Windows CPython 3.13 x64.
# Does not contact or modify gateways, credentials or Amazon Quick.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedCommit,
  [string]$Destination = (Join-Path $HOME 'Quick-Wrapper-B4g') ,
  [switch]$NoLaunch
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoUrl='https://github.com/askjake/Quick-Wrapper.git'
$branch='release/windows-b4g-20261102'
$zipRel='releases/windows-b4g/B4G_FROZEN_TREE.zip'
$expectedZip='d0ece5261244f23b886e0cb1cc446e6911734cd702aeb152bfde8e510e675a29'
$expectedManifest='dec25425872676b0eba42b3600dfb7070a7881305749575b24e0ad899ab49d35'
$expectedSource='e8413e60d535e6961947627fa44b25121df474000fc9d57f2f5113e612b27935'
$expectedTree='bbce64f8deda1ea078a8715d6813476a333110284afcdefb5c3db1f47a4620d0'
function CheckExit([string]$step) { if ($LASTEXITCODE -ne 0) { throw "$step failed with exit $LASTEXITCODE" } }
function SHA([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git not available; nothing installed' }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python launcher unavailable; require approved CPython 3.13 x64' }
& py -3.13 -c 'import sys,platform,tkinter; assert sys.implementation.name=="cpython" and sys.version_info[:2]==(3,13) and sys.platform=="win32" and platform.architecture()[0]=="64bit"; print("PYTHON313_WINDOWS_TK_OK")'
CheckExit 'Python/Tk admission'
if (Test-Path -LiteralPath $Destination) { throw "Destination exists; refusing to overwrite: $Destination" }
$parent=Split-Path -Parent $Destination
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw "Destination parent does not exist: $parent" }
& git clone --single-branch --branch $branch -- $repoUrl $Destination
CheckExit 'Clone team release'
Push-Location -LiteralPath $Destination
try {
  $head=(& git rev-parse HEAD).Trim();CheckExit 'Read commit'
  if ($head -ne $ExpectedCommit.ToLowerInvariant()) { throw "Unapproved release commit $head; do not continue" }
  $zipPath=Join-Path $Destination $zipRel
  if ((SHA $zipPath) -ne $expectedZip) { throw 'Release ZIP SHA-256 mismatch; no extraction' }
  $app=Join-Path $Destination 'app'
  if (Test-Path -LiteralPath $app) { throw 'Application folder already exists' }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $app
  $manifestPath=Join-Path $app 'B4G_FROZEN_TREE_MANIFEST.json'
  if ((SHA $manifestPath) -ne $expectedManifest) { throw 'Embedded release manifest SHA-256 mismatch' }
  $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.schema -ne 'AQ_B4g_frozen_tree_v1' -or $manifest.source_archive_sha256 -ne $expectedSource -or $manifest.tree_digest -ne $expectedTree -or $manifest.tree_files -ne 67) { throw 'Frozen manifest identity mismatch' }
  $tree=Join-Path $app 'tree'
  $seen=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  $recordHash=@{}
  foreach ($row in $manifest.files) {
    $rel=[string]$row.path
    if ($rel.StartsWith('/') -or $rel.Contains('..') -or $rel -notmatch '^[A-Za-z0-9_.\-/]+$' -or -not $seen.Add($rel)) { throw "Unsafe or duplicate source path $rel" }
    $path=Join-Path $tree ($rel.Replace('/',[IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Source file missing: $rel" }
    if ((SHA $path) -ne [string]$row.sha256 -or (Get-Item -LiteralPath $path).Length -ne [long]$row.size) { throw "Source file mismatch: $rel" }
    $recordHash[$rel]=[string]$row.sha256
  }
  if ($seen.Count -ne 67) { throw 'Unexpected source member count' }
  $names=[string[]]@($recordHash.Keys);[Array]::Sort($names,[StringComparer]::Ordinal)
  $lines=New-Object 'System.Collections.Generic.List[string]'
  foreach($name in $names) { $lines.Add("$($recordHash[$name])  $name") }
  $canonical=[String]::Join("`n",$lines)
  $hashObj=[Security.Cryptography.SHA256]::Create()
  try { $digest=([BitConverter]::ToString($hashObj.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-','').ToLowerInvariant() }
  finally { $hashObj.Dispose() }
  if ($digest -ne $expectedTree) { throw 'Frozen tree digest mismatch' }
  Write-Host "B4G_SOURCE_VERIFIED commit=$head files=67 tree=$digest"
  $venv=Join-Path $Destination '.venv'
  & py -3.13 -m venv $venv; CheckExit 'Create project-local virtual environment'
  $python=Join-Path $venv 'Scripts\python.exe'
  & $python -m pip install -r (Join-Path $tree 'requirements.txt'); CheckExit 'Install requirements'
  Push-Location -LiteralPath $tree
  try {
    & $python -c 'import tkinter,paramiko,cli,wizard,native_gateway; print("B4G_IMPORT_SMOKE_PASS")';CheckExit 'Import smoke'
    Write-Host "B4G_INSTALLED_FROM_PINNED_GITHUB_COMMIT=$head"
    if (-not $NoLaunch) { & $python 'wizard.py'; CheckExit 'Wizard exit' }
  } finally { Pop-Location }
} finally { Pop-Location }
