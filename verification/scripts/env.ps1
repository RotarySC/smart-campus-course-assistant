<#
  env.ps1 -- Phase 5 independent verification environment (qa-verifier only).

  Everything here is isolated from the Lead's environment:
    DB      : cca_test_release (127.0.0.1:33061)
    public  : 127.0.0.1:8200
    internal: 127.0.0.1:8201
    MCP     : 127.0.0.1:8202
    frontend: 127.0.0.1:5273 (Vite proxy -> 8200)
    files   : verification/runtime/filestore
    vectors : verification/runtime/vector

  DO NOT touch 8100/8101/8102, 5173, database cca, or backend/uploads.

  Services are launched through generated .cmd wrappers (verification/runtime/launchers/),
  with stdout/stderr redirected to verification/runtime/logs/. PIDs are recorded and the
  whole process tree is killed on stop (the venv python.exe re-execs the base interpreter,
  so the listener is a grandchild of the launcher).

  Usage (from anywhere; paths resolve from the script location):
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action env        # print env block
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action prepare    # create DB if missing + alembic upgrade head
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action start      # start public/internal/mcp/worker
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action status     # ports + pids + /health
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action stop       # stop all recorded services (process tree)
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action reset-db -Confirm   # downgrade base + upgrade head (DESTRUCTIVE)
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action seed       # demo seed into cca_test_release
    pwsh -NoProfile -File verification/scripts/env.ps1 -Action worker-once # one worker drain round (foreground)
#>
param(
  [ValidateSet('env', 'prepare', 'start', 'status', 'stop', 'reset-db', 'seed', 'worker-once')]
  [string]$Action = 'env',
  [switch]$Confirm
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$Backend   = Join-Path $RepoRoot 'backend'
$Py        = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Runtime   = Join-Path $RepoRoot 'verification\runtime'
$Filestore = Join-Path $Runtime 'filestore'
$Vector    = Join-Path $Runtime 'vector'
$PidDir    = Join-Path $Runtime 'pids'
$LogDir    = Join-Path $Runtime 'logs'
$LaunchDir = Join-Path $Runtime 'launchers'

$DatabaseUrl = 'mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_release?charset=utf8mb4'

$Services = @(
  @{ Name = 'public';   Port = 8200; Marker = 'app.entrypoints.public_api';   Args = @('-m', 'uvicorn', 'app.entrypoints.public_api:app',   '--host', '127.0.0.1', '--port', '8200') },
  @{ Name = 'internal'; Port = 8201; Marker = 'app.entrypoints.internal_api'; Args = @('-m', 'uvicorn', 'app.entrypoints.internal_api:app', '--host', '127.0.0.1', '--port', '8201') },
  @{ Name = 'mcp';      Port = 8202; Marker = 'app.entrypoints.mcp_server';   Args = @('-m', 'app.entrypoints.mcp_server') },
  @{ Name = 'worker';   Port = 0;    Marker = 'app.entrypoints.worker';       Args = @('-m', 'app.entrypoints.worker', '--poll-seconds', '1') }
)

function Set-VerificationEnv {
  # CCA_ENV=dev on purpose: services must use the pooled engine (production-like),
  # while pytest uses CCA_ENV=test (NullPool) via its own process env.
  $env:DATABASE_URL             = $DatabaseUrl
  $env:CCA_ENV                  = 'dev'
  $env:CCA_SCHOOL_TIMEZONE      = 'Asia/Shanghai'
  $env:CCA_FILESTORE_ROOT       = $Filestore
  $env:CCA_VECTOR_ROOT          = $Vector
  $env:CCA_INTERNAL_API_URL     = 'http://127.0.0.1:8201'
  $env:CCA_MCP_URL              = 'http://127.0.0.1:8202/mcp'
  $env:CCA_MCP_HOST             = '127.0.0.1'
  $env:CCA_MCP_PORT             = '8202'
  $env:CCA_MCP_PATH             = '/mcp'
  $env:CCA_CORS_ORIGINS         = 'http://localhost:5273,http://127.0.0.1:5273'
}

function Initialize-Dirs {
  foreach ($d in @($Runtime, $Filestore, $Vector, $PidDir, $LogDir, $LaunchDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
  }
}

function Get-PortState([int]$Port) {
  return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Write-Launcher([hashtable]$Svc) {
  $path = Join-Path $LaunchDir ($Svc.Name + '.cmd')
  $out = Join-Path $LogDir ($Svc.Name + '.log')
  $lines = @(
    '@echo off',
    ('cd /d "' + $Backend + '"'),
    ('set "DATABASE_URL=' + $DatabaseUrl + '"'),
    'set "CCA_ENV=dev"',
    'set "CCA_SCHOOL_TIMEZONE=Asia/Shanghai"',
    ('set "CCA_FILESTORE_ROOT=' + $Filestore + '"'),
    ('set "CCA_VECTOR_ROOT=' + $Vector + '"'),
    'set "CCA_INTERNAL_API_URL=http://127.0.0.1:8201"',
    'set "CCA_MCP_URL=http://127.0.0.1:8202/mcp"',
    'set "CCA_MCP_HOST=127.0.0.1"',
    'set "CCA_MCP_PORT=8202"',
    'set "CCA_MCP_PATH=/mcp"',
    'set "CCA_CORS_ORIGINS=http://localhost:5273,http://127.0.0.1:5273"',
    ('"' + $Py + '" ' + ($Svc.Args -join ' ') + ' >> "' + $out + '" 2>&1')
  )
  Set-Content -Path $path -Value $lines -Encoding ASCII
  return $path
}

function Get-DescendantIds([int]$RootPid) {
  $all = Get-CimInstance Win32_Process
  $found = New-Object System.Collections.Generic.List[int]
  $queue = New-Object System.Collections.Generic.Queue[int]
  $queue.Enqueue($RootPid)
  while ($queue.Count -gt 0) {
    $current = $queue.Dequeue()
    foreach ($child in ($all | Where-Object { $_.ParentProcessId -eq $current })) {
      $found.Add([int]$child.ProcessId)
      $queue.Enqueue([int]$child.ProcessId)
    }
  }
  return $found.ToArray()
}

function Invoke-EnvPrint {
  Write-Output '--- verification environment (PowerShell) ---'
  Write-Output ('$env:DATABASE_URL         = "' + $DatabaseUrl + '"')
  Write-Output '$env:CCA_ENV              = "dev"        # pytest: "test"'
  Write-Output ('$env:CCA_FILESTORE_ROOT   = "' + $Filestore + '"')
  Write-Output ('$env:CCA_VECTOR_ROOT      = "' + $Vector + '"')
  Write-Output '$env:CCA_INTERNAL_API_URL = "http://127.0.0.1:8201"'
  Write-Output '$env:CCA_MCP_URL          = "http://127.0.0.1:8202/mcp"'
  Write-Output '$env:CCA_MCP_PORT         = "8202"'
  Write-Output '$env:CCA_CORS_ORIGINS     = "http://localhost:5273,http://127.0.0.1:5273"'
  Write-Output '$env:VITE_DEV_PROXY       = "http://127.0.0.1:8200"   # for pnpm dev on 5273'
  Write-Output '$env:E2E_BASE             = "http://127.0.0.1:8200/api/v1"'
  Write-Output '$env:BACKEND_BASE         = "http://127.0.0.1:8200/api/v1"'
  Write-Output '$env:WEB_BASE             = "http://localhost:5273"'
  Write-Output '--- ports ---'
  Write-Output 'public 8200 / internal 8201 / mcp 8202 / frontend 5273'
}

function Invoke-Prepare {
  Initialize-Dirs
  Set-VerificationEnv
  Write-Output '[prepare] ensuring database cca_test_release exists'
  $sql = "CREATE DATABASE IF NOT EXISTS cca_test_release CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;"
  docker exec cca-mysql mysql -uroot -pcca_dev_root -e $sql 2>$null
  if ($LASTEXITCODE -ne 0) { throw 'docker exec cca-mysql failed (is the container running?)' }
  Push-Location $Backend
  try {
    Write-Output '[prepare] alembic upgrade head'
    & $Py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade head failed' }
    Write-Output ('[prepare] python=' + (& $Py -c 'import sys;print(sys.version.split()[0])'))
    Write-Output ('[prepare] alembic current: ' + (& $Py -m alembic current 2>&1))
  } finally { Pop-Location }
  $count = docker exec cca-mysql mysql -uroot -pcca_dev_root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cca_test_release';" 2>$null
  Write-Output ('[prepare] cca_test_release tables (incl. alembic_version): ' + ($count | Select-Object -Last 1))
}

function Invoke-Start {
  Initialize-Dirs
  Set-VerificationEnv
  foreach ($svc in $Services) {
    $pidFile = Join-Path $PidDir ($svc.Name + '.pid')
    if (Test-Path $pidFile) {
      $old = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
      $alive = if ($old) { Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue } else { $null }
      $treeAlive = if ($alive) { @(Get-DescendantIds ([int]$old) | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }) } else { @() }
      if ($alive -or $treeAlive.Count -gt 0) { Write-Output ('[start] ' + $svc.Name + ' already running pid=' + $old); continue }
      Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    if ($svc.Port -gt 0 -and (Get-PortState $svc.Port)) {
      throw ('[start] port ' + $svc.Port + ' already in use by pid=' + (Get-PortState $svc.Port).OwningProcess + '; refusing to start ' + $svc.Name)
    }
    $launcher = Write-Launcher $svc
    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', ('"' + $launcher + '"') `
      -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $LogDir ($svc.Name + '.cmd.out.log')) `
      -RedirectStandardError  (Join-Path $LogDir ($svc.Name + '.cmd.err.log'))
    Set-Content -Path $pidFile -Value $proc.Id
    Write-Output ('[start] ' + $svc.Name + ' launcher_pid=' + $proc.Id + ' log=' + (Join-Path $LogDir ($svc.Name + '.log')))
    if ($svc.Port -gt 0) { Start-Sleep -Milliseconds 1500 }
  }
}

function Invoke-Status {
  Set-VerificationEnv
  foreach ($svc in $Services) {
    $pidFile = Join-Path $PidDir ($svc.Name + '.pid')
    $pidText = if (Test-Path $pidFile) { (Get-Content $pidFile | Select-Object -First 1) } else { '' }
    $listen = if ($svc.Port -gt 0) { Get-PortState $svc.Port } else { $null }
    Write-Output ('[' + $svc.Name + '] launcher_pid=' + $(if ($pidText) { $pidText } else { '-' }) + ' port=' + $svc.Port + ' listening=' + $(if ($svc.Port -eq 0) { 'n/a' } elseif ($listen) { 'yes(pid=' + $listen.OwningProcess + ')' } else { 'NO' }))
  }
  try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8200/api/v1/health' -TimeoutSec 5
    Write-Output ('[health] ' + ($health | ConvertTo-Json -Compress -Depth 5))
  } catch { Write-Output ('[health] FAILED: ' + $_.Exception.Message) }
  try {
    $openapi = Invoke-RestMethod -Uri 'http://127.0.0.1:8200/api/v1/openapi.json' -TimeoutSec 10
    Write-Output ('[openapi] paths=' + @($openapi.paths.PSObject.Properties).Count)
  } catch { Write-Output ('[openapi] FAILED: ' + $_.Exception.Message) }
  try {
    $internal = Invoke-RestMethod -Uri 'http://127.0.0.1:8201/internal/v1/openapi.json' -TimeoutSec 10
    Write-Output ('[internal openapi] paths=' + @($internal.paths.PSObject.Properties).Count)
  } catch { Write-Output ('[internal openapi] note: ' + $_.Exception.Message) }
}

function Invoke-Stop {
  foreach ($svc in $Services) {
    $pidFile = Join-Path $PidDir ($svc.Name + '.pid')
    if (-not (Test-Path $pidFile)) { Write-Output ('[stop] ' + $svc.Name + ' not started by this script'); continue }
    $pidText = Get-Content $pidFile | Select-Object -First 1
    $rootPid = [int]$pidText
    $desc = @(Get-DescendantIds $rootPid)
    foreach ($d in $desc) { Stop-Process -Id $d -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $rootPid -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Write-Output ('[stop] ' + $svc.Name + ' killed tree root=' + $rootPid + ' descendants=' + ($desc -join ','))
  }
  Start-Sleep -Milliseconds 500
  foreach ($svc in $Services) {
    if ($svc.Port -gt 0 -and (Get-PortState $svc.Port)) {
      Write-Output ('[stop] WARNING port ' + $svc.Port + ' still listening pid=' + (Get-PortState $svc.Port).OwningProcess)
    }
  }
}

function Assert-SafeDatabase([string]$Url) {
  if ($Url -notmatch '/cca_test_release\?') { throw ('refusing to run destructive command against: ' + $Url) }
}

function Invoke-ResetDb {
  if (-not $Confirm) { throw 'reset-db is destructive (downgrade base = drops all tables). Re-run with -Confirm.' }
  Assert-SafeDatabase $DatabaseUrl
  Initialize-Dirs
  Set-VerificationEnv
  Push-Location $Backend
  try {
    Write-Output '[reset-db] alembic downgrade base'
    & $Py -m alembic downgrade base
    if ($LASTEXITCODE -ne 0) { throw 'downgrade base failed' }
    Write-Output '[reset-db] alembic upgrade head'
    & $Py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'upgrade head failed' }
  } finally { Pop-Location }
  $count = docker exec cca-mysql mysql -uroot -pcca_dev_root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cca_test_release';" 2>$null
  Write-Output ('[reset-db] tables (incl. alembic_version): ' + ($count | Select-Object -Last 1))
}

function Invoke-Seed {
  Set-VerificationEnv
  Initialize-Dirs
  Push-Location $Backend
  try {
    Write-Output '[seed] app.cli.seed --demo (into cca_test_release only)'
    & $Py -m app.cli.seed --demo
    if ($LASTEXITCODE -ne 0) { throw 'seed failed' }
  } finally { Pop-Location }
}

function Invoke-WorkerOnce {
  Set-VerificationEnv
  Push-Location $Backend
  try {
    & $Py -m app.entrypoints.worker --once
    if ($LASTEXITCODE -ne 0) { throw 'worker --once failed' }
  } finally { Pop-Location }
}

switch ($Action) {
  'env'         { Invoke-EnvPrint }
  'prepare'     { Invoke-Prepare }
  'start'       { Invoke-Start }
  'status'      { Invoke-Status }
  'stop'        { Invoke-Stop }
  'reset-db'    { Invoke-ResetDb }
  'seed'        { Invoke-Seed }
  'worker-once' { Invoke-WorkerOnce }
}
