#Requires -Version 7.0

<#
.SYNOPSIS
    校园课程智能助手 · 一键启动（MySQL 容器 + 后端四服务 + 前端 dev server）

.DESCRIPTION
    按 docs/STARTUP.md 的启动顺序执行，全部为幂等步骤：

      1. 前置检查：.venv / backend/.env / Docker（可跳过）/ 端口
      2. MySQL：拉起容器 cca-mysql（不存在则按国内镜像创建），等就绪，确保演示库 cca 存在
      3. 迁移：alembic upgrade head（-ResetDb 时先 downgrade base）
      4. 种子：python -m app.cli.seed --demo（可跳过）
      5. 后端四进程：public 8100 / internal 8101 / mcp 8102 / worker（后台，PID 与日志落 backend/var）
      6. 前端：pnpm dev（默认连真实后端，-Mock 时切 mock 夹具）
      7. 健康检查并打印访问入口

    所有进程都在后台运行，PID 写入 backend/var/run/*.pid，日志写入 backend/var/logs/*.log。
    停止用 scripts/stop.ps1，巡检用 scripts/status.ps1。

.PARAMETER PublicPort
    公共 API 端口，默认 8100（契约与前端 proxy 的默认值，一般不要改）。

.PARAMETER InternalPort
    内部 API 端口，默认 8101（只回环）。

.PARAMETER McpPort
    MCP server 端口，默认 8102（只回环）。

.PARAMETER WebPort
    前端 dev server 端口，默认 5173。

.PARAMETER NoFrontend
    只起后端，不起前端。

.PARAMETER Mock
    前端走 mock 传输层（VITE_USE_MOCK=true）。仅用于无后端时调 UI，验收口径永远是真实后端。

.PARAMETER SkipSeed
    跳过开发种子（不动 demo 账号/课程/课表）。

.PARAMETER SkipDocker
    不检查/不拉起 MySQL 容器（数据库已在别处运行时用）。

.PARAMETER ResetDb
    迁移前先 downgrade base（**会清空演示库 cca 的全部表与数据**），再 upgrade head。

.PARAMETER SkipInstall
    前端缺依赖时不自动 pnpm install，直接报错。

.PARAMETER WaitSeconds
    各服务就绪等待上限（秒），默认 90。

.EXAMPLE
    .\scripts\start.ps1
    起全套（MySQL + 后端 + 前端），打印入口。

.EXAMPLE
    .\scripts\start.ps1 -NoFrontend
    只起后端（CI/接口调试常用）。

.EXAMPLE
    .\scripts\start.ps1 -ResetDb -SkipSeed
    演示库推倒重建迁移，不写种子。

.EXAMPLE
    .\scripts\start.ps1 -NoFrontend -PublicPort 8200 -InternalPort 8201 -McpPort 8202
    换一套端口起后端，避免和已运行实例撞端口（独立验证常用）。
#>
[CmdletBinding()]
param(
    [int]$PublicPort = 8100,
    [int]$InternalPort = 8101,
    [int]$McpPort = 8102,
    [int]$WebPort = 5173,
    [switch]$NoFrontend,
    [switch]$Mock,
    [switch]$SkipSeed,
    [switch]$SkipDocker,
    [switch]$ResetDb,
    [switch]$SkipInstall,
    [int]$WaitSeconds = 90
)

$ErrorActionPreference = 'Stop'

# --------------------------------------------------------------------------- #
# 路径与常量
# --------------------------------------------------------------------------- #
$Root      = Split-Path -Parent $PSScriptRoot
$Backend   = Join-Path $Root 'backend'
$Web       = Join-Path $Root 'web'
$Py        = Join-Path $Root '.venv\Scripts\python.exe'
$EnvFile   = Join-Path $Backend '.env'
$RunDir    = Join-Path $Backend 'var\run'
$LogDir    = Join-Path $Backend 'var\logs'
$Container = 'cca-mysql'
$Image     = 'docker.m.daocloud.io/library/mysql:8.4'
$MysqlRoot = 'cca_dev_root'
$DemoUrl   = 'mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca?charset=utf8mb4'

New-Item -ItemType Directory -Force -Path $RunDir, $LogDir | Out-Null
# 给子进程一个独立的空 stdin：否则调用方用管道捕获脚本输出时，
# 后台服务的句柄继承会拖住管道读取（CI/管道场景会一直等到超时）。
$EmptyInput = Join-Path $LogDir 'empty.stdin'
if (-not (Test-Path $EmptyInput)) { Set-Content -Path $EmptyInput -Value '' -Encoding ascii -NoNewline }

# --------------------------------------------------------------------------- #
# 输出助手
# --------------------------------------------------------------------------- #
function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text)   { Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text){ Write-Host "  [WARN] $Text" -ForegroundColor Yellow }
function Write-Fail([string]$Text) { Write-Host "  [FAIL] $Text" -ForegroundColor Red }
function Stop-WithError([string]$Text) { Write-Fail $Text; exit 1 }

# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
function Test-Port([int]$Port) {
    if ($Port -le 0) { return $false }
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# Docker Desktop 的端口转发不一定出现在 Get-NetTCPConnection 里（WSL 中继），
# 容器端口用真实 TCP 连接判断。
function Test-TcpConnect([string]$TargetHost, [int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($TargetHost, $Port)
        if (-not $task.Wait(800)) { return $false }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-EnvValue([string]$File, [string]$Key) {
    if (-not (Test-Path $File)) { return $null }
    $line = Get-Content $File -Encoding utf8 |
        Where-Object { $_ -match ("^\s*" + [regex]::Escape($Key) + "\s*=") } |
        Select-Object -Last 1
    if (-not $line) { return $null }
    return (($line -replace '^\s*[^=]+=', '').Trim().Trim('"').Trim("'"))
}

function Wait-Tcp([int]$Port, [string]$Name, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Milliseconds 400
    }
    Write-Warn2 "$Name（端口 $Port）在 ${TimeoutSeconds}s 内未就绪"
    return $false
}

function Wait-Http([string]$Url, [string]$Name, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -lt 500) { return $true }
        } catch {
            # 服务还没起来：继续等
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Warn2 "$Name（$Url）在 ${TimeoutSeconds}s 内未通过健康检查"
    return $false
}

# 非默认端口时 PID/日志名带端口后缀，避免两套实例互相覆盖（8100 与 8200 可并存）。
function Get-InstanceStem([string]$Name, [int]$Port, [int]$DefaultPort) {
    if ($Port -gt 0 -and $Port -ne $DefaultPort) { return "$Name-$Port" }
    return $Name
}

function Get-RecordedPid([string]$Name) {
    $file = Join-Path $RunDir "$Name.pid"
    if (-not (Test-Path $file)) { return $null }
    $raw = (Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $raw) { return $null }
    $procId = 0
    if (-not [int]::TryParse($raw.Trim(), [ref]$procId)) { return $null }
    if (Get-Process -Id $procId -ErrorAction SilentlyContinue) { return $procId }
    return $null
}

function Start-BackendService([string]$Name, [string]$Label, [int]$Port, [string[]]$Arguments, [int]$DefaultPort = 0) {
    if ($Port -gt 0 -and (Test-Port $Port)) {
        Write-Warn2 "$Label：端口 $Port 已被占用，视为已在运行，跳过启动"
        return 'skipped'
    }
    $stem = Get-InstanceStem $Name $Port $DefaultPort
    $existing = Get-RecordedPid $stem
    if ($Port -le 0 -and $existing) {
        Write-Warn2 "$Label：已在运行（PID $existing），跳过启动"
        return 'skipped'
    }

    $outLog = Join-Path $LogDir "$stem.out.log"
    $errLog = Join-Path $LogDir "$stem.err.log"
    $proc = Start-Process -FilePath $Py -ArgumentList $Arguments `
        -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
        -RedirectStandardInput $EmptyInput `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Set-Content -Path (Join-Path $RunDir "$stem.pid") -Value $proc.Id -Encoding ascii
    Write-Ok "$Label 已启动（PID $($proc.Id)，端口 $Port）"
    return 'started'
}

# --------------------------------------------------------------------------- #
# 0. 前置检查
# --------------------------------------------------------------------------- #
Write-Host ''
Write-Host '校园课程智能助手 · 一键启动' -ForegroundColor White
Write-Host "仓库根：$Root"

Write-Step '0/6 前置检查'
if (-not (Test-Path $Py)) {
    Stop-WithError "找不到 Python 虚拟环境：$Py`n        请先创建并安装依赖：python -m venv .venv；然后 .venv\Scripts\python.exe -m pip install -e backend"
}
Write-Ok "Python：$Py"

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) { Write-Ok "Node：$(& node --version)" } elseif (-not $NoFrontend) { Write-Warn2 '未找到 node（前端将无法启动）' }

$pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if (-not $pnpm) { $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue }
if ($pnpm -and -not $NoFrontend) { Write-Ok "pnpm：$(& $pnpm.Source --version)" }

foreach ($p in @(@{P=$PublicPort;N='公共 API'}, @{P=$InternalPort;N='内部 API'}, @{P=$McpPort;N='MCP'}, @{P=$WebPort;N='前端'})) {
    if ($p.P -eq $WebPort -and $NoFrontend) { continue }
    if (Test-Port $p.P) { Write-Warn2 "$($p.N) 端口 $($p.P) 已有进程监听（将复用或跳过，详见下文）" }
}

# --------------------------------------------------------------------------- #
# 1. MySQL
# --------------------------------------------------------------------------- #
if (-not $SkipDocker) {
    Write-Step '1/6 MySQL（容器 cca-mysql）'
    docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError 'Docker 引擎不可用：请先启动 Docker Desktop，或加 -SkipDocker 使用已有数据库'
    }

    docker inspect $Container --format '{{.State.Running}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "容器不存在，按国内镜像创建：$Image"
        $runArgs = @(
            'run', '-d', '--name', $Container, '--restart', 'unless-stopped',
            '-e', "MYSQL_ROOT_PASSWORD=$MysqlRoot",
            '-e', 'MYSQL_DATABASE=cca',
            '-e', 'TZ=UTC',
            '-p', '127.0.0.1:33061:3306',
            $Image
        )
        & docker @runArgs | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-WithError '容器创建失败（端口 33061 可能被占用，或镜像拉取失败）' }
        Write-Ok "容器已创建：$Container"
    } else {
        $running = (docker inspect $Container --format '{{.State.Running}}').Trim()
        if ($running -ne 'true') {
            & docker start $Container | Out-Null
            if ($LASTEXITCODE -ne 0) { Stop-WithError "容器 $Container 启动失败" }
            Write-Ok "容器已启动：$Container"
        } else {
            Write-Ok "容器已在运行：$Container"
        }
    }

    $deadline = (Get-Date).AddSeconds([Math]::Max(30, $WaitSeconds))
    $mysqlReady = $false
    while ((Get-Date) -lt $deadline) {
        & docker exec $Container mysqladmin ping -h 127.0.0.1 -uroot "-p$MysqlRoot" --silent 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $mysqlReady = $true; break }
        Start-Sleep -Milliseconds 800
    }
    if (-not $mysqlReady) { Stop-WithError "MySQL 在 ${WaitSeconds}s 内未就绪；看日志：docker logs $Container" }
    Write-Ok 'MySQL 已就绪（127.0.0.1:33061）'

    & docker exec $Container mysql -uroot "-p$MysqlRoot" -e `
        'CREATE DATABASE IF NOT EXISTS cca DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warn2 '演示库 cca 创建/校验失败（若已存在可忽略）' }
    else { Write-Ok '演示库 cca 存在（utf8mb4_0900_bin）' }
} else {
    Write-Step '1/6 MySQL（-SkipDocker：跳过容器管理）'
    if (-not (Test-TcpConnect '127.0.0.1' 33061)) { Write-Warn2 '端口 33061 未监听，确认 DATABASE_URL 指向的数据库可用' }
}

# --------------------------------------------------------------------------- #
# 2. 配置与迁移
# --------------------------------------------------------------------------- #
Write-Step '2/6 配置（backend/.env）'
if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path (Join-Path $Backend '.env.example'))) { Stop-WithError '缺少 backend/.env.example' }
    $lines = Get-Content (Join-Path $Backend '.env.example') -Encoding utf8 | ForEach-Object {
        if ($_ -match '^\s*DATABASE_URL\s*=') { "DATABASE_URL=$DemoUrl" } else { $_ }
    }
    Set-Content -Path $EnvFile -Value $lines -Encoding utf8NoBOM
    Write-Ok '已由 .env.example 生成 backend/.env（DATABASE_URL → 演示库 cca）'
} else {
    Write-Ok 'backend/.env 已存在（沿用其中配置；进程环境变量优先）'
}

$dbUrl = Get-EnvValue $EnvFile 'DATABASE_URL'
if (-not $dbUrl) { $dbUrl = $DemoUrl }

# 已显式设置的 DATABASE_URL（进程环境变量）优先——多实例/CI 用它切库，脚本不覆盖。
if ($env:DATABASE_URL) {
    $effectiveDbUrl = $env:DATABASE_URL
    if ($effectiveDbUrl -ne $dbUrl) {
        Write-Warn2 '使用进程环境变量 DATABASE_URL（覆盖 backend/.env 的值）'
    }
} else {
    $effectiveDbUrl = $dbUrl
}
$env:DATABASE_URL = $effectiveDbUrl
$dbName = ($effectiveDbUrl -split '/')[-1].Split('?')[0]
if ($dbName -match '^cca_test_') {
    Write-Warn2 "DATABASE_URL 指向测试库 $dbName（测试夹具会清表）；演示数据请用 .../cca"
}

Write-Step '3/6 数据库迁移'
Push-Location $Backend
try {
    if ($ResetDb) {
        Write-Warn2 'ResetDb：先 downgrade base（清空当前库全部表）'
        & $Py -m alembic downgrade base
        if ($LASTEXITCODE -ne 0) { Stop-WithError 'alembic downgrade base 失败' }
    }
    & $Py -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'alembic upgrade head 失败（往上翻日志）' }
    Write-Ok "迁移完成：$dbName"
} finally {
    Pop-Location
}

# --------------------------------------------------------------------------- #
# 3. 种子
# --------------------------------------------------------------------------- #
Write-Step '4/6 开发种子'
if ($SkipSeed) {
    Write-Warn2 '已跳过（-SkipSeed）'
} else {
    Push-Location $Backend
    try {
        & $Py -m app.cli.seed --demo
        if ($LASTEXITCODE -ne 0) { Stop-WithError '种子写入失败' }
        Write-Ok '种子就绪：student_demo / admin_demo（口令 demo1234，仅开发）'
    } finally {
        Pop-Location
    }
}

# --------------------------------------------------------------------------- #
# 4. 后端服务
# --------------------------------------------------------------------------- #
Write-Step '5/6 后端服务（public / internal / mcp / worker）'
$env:CCA_MCP_PORT = "$McpPort"
$env:CCA_MCP_URL = "http://127.0.0.1:$McpPort/mcp"
$env:CCA_INTERNAL_API_URL = "http://127.0.0.1:$InternalPort"
$env:CCA_CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort"

$results = [ordered]@{}
if ($InternalPort -ne 8101 -or $PublicPort -ne 8100 -or $McpPort -ne 8102) {
    Write-Warn2 "使用非默认端口：前端 proxy/内部调用已按参数覆盖（CCA_* 环境变量）"
}

$results['public']   = Start-BackendService -Name 'public' -Label '公共 API' -Port $PublicPort -DefaultPort 8100 `
    -Arguments @('-m', 'uvicorn', 'app.entrypoints.public_api:app', '--host', '127.0.0.1', '--port', "$PublicPort")
$results['internal'] = Start-BackendService -Name 'internal' -Label '内部 API' -Port $InternalPort -DefaultPort 8101 `
    -Arguments @('-m', 'uvicorn', 'app.entrypoints.internal_api:app', '--host', '127.0.0.1', '--port', "$InternalPort")
$results['mcp']      = Start-BackendService -Name 'mcp' -Label 'MCP server' -Port $McpPort -DefaultPort 8102 `
    -Arguments @('-m', 'app.entrypoints.mcp_server')
# Worker 没有端口，用公共 API 端口区分实例（默认 8100 时仍叫 worker）。
$workerStem = if ($PublicPort -eq 8100) { 'worker' } else { "worker-$PublicPort" }
$results['worker']   = Start-BackendService -Name $workerStem -Label '文档 Worker' -Port 0 `
    -Arguments @('-m', 'app.entrypoints.worker')

$healthy = $true
if (-not (Wait-Http "http://127.0.0.1:$PublicPort/api/v1/health" '公共 API' $WaitSeconds)) { $healthy = $false }
if (-not (Wait-Tcp $InternalPort '内部 API' 30)) { $healthy = $false }
if (-not (Wait-Tcp $McpPort 'MCP server' 30)) { $healthy = $false }
if ($healthy) { Write-Ok '后端四服务就绪' }

# --------------------------------------------------------------------------- #
# 5. 前端
# --------------------------------------------------------------------------- #
$webStarted = $false
if ($NoFrontend) {
    Write-Step '6/6 前端（-NoFrontend：跳过）'
} else {
    Write-Step '6/6 前端 dev server'
    if (-not $pnpm) { Stop-WithError '未找到 pnpm：请先 npm i -g pnpm，或用 -NoFrontend 只起后端' }
    if (-not (Test-Path (Join-Path $Web 'node_modules'))) {
        if ($SkipInstall) { Stop-WithError 'web/node_modules 缺失且指定了 -SkipInstall' }
        Write-Warn2 'web/node_modules 缺失，执行 pnpm install（registry.npmmirror.com）'
        Push-Location $Web
        try {
            & $pnpm.Source install --prefer-offline
            if ($LASTEXITCODE -ne 0) { Stop-WithError 'pnpm install 失败' }
        } finally { Pop-Location }
    }
    if (Test-Port $WebPort) {
        Write-Warn2 "前端端口 $WebPort 已被占用，跳过启动（如为旧实例请先 scripts/stop.ps1）"
        $webStarted = $true
    } else {
        $env:VITE_USE_MOCK = if ($Mock) { 'true' } else { 'false' }
        $env:VITE_DEV_PROXY = "http://127.0.0.1:$PublicPort"
        # 前端 PID 用公共 API 端口区分实例（默认 8100 时叫 web），避免停 8200 那套时误杀默认实例。
        $webStem = if ($PublicPort -eq 8100) { 'web' } else { "web-$PublicPort" }
        $outLog = Join-Path $LogDir "$webStem.out.log"
        $errLog = Join-Path $LogDir "$webStem.err.log"
        # pnpm 可能是 pnpm.cmd（首选）或 pnpm.ps1（只有 PS 垫片时用 pwsh 包一层）。
        $pnpmExe = $pnpm.Source
        $pnpmArgs = @('dev', '--port', "$WebPort", '--strictPort')
        if ($pnpmExe -like '*.ps1') {
            $pnpmArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $pnpmExe) + $pnpmArgs
            $pnpmExe = 'pwsh'
        }
        $webProc = Start-Process -FilePath $pnpmExe -ArgumentList $pnpmArgs `
            -WorkingDirectory $Web -WindowStyle Hidden -PassThru `
            -RedirectStandardInput $EmptyInput `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog
        Set-Content -Path (Join-Path $RunDir "$webStem.pid") -Value $webProc.Id -Encoding ascii
        Write-Ok "前端已启动（PID $($webProc.Id)，mock=$($env:VITE_USE_MOCK)）"
        # 注意：Vite 默认只绑定 localhost（本机解析到 ::1），用 127.0.0.1 探活会被拒连。
        if (Wait-Http "http://localhost:$WebPort/" '前端' 90) { $webStarted = $true }
    }
}

# --------------------------------------------------------------------------- #
# 6. 汇总
# --------------------------------------------------------------------------- #
Write-Host ''
Write-Host '================== 启动结果 ==================' -ForegroundColor White
$rows = New-Object System.Collections.Generic.List[object]
$rows.Add([pscustomobject]@{ 服务 = '公共 API'; 地址 = "http://127.0.0.1:$PublicPort/api/v1"; 状态 = if (Test-Port $PublicPort) { 'UP' } else { 'DOWN' } })
$rows.Add([pscustomobject]@{ 服务 = '健康检查'; 地址 = "http://127.0.0.1:$PublicPort/api/v1/health"; 状态 = if ($healthy) { 'UP' } else { 'DOWN' } })
$rows.Add([pscustomobject]@{ 服务 = '内部 API'; 地址 = "http://127.0.0.1:$InternalPort/internal/v1"; 状态 = if (Test-Port $InternalPort) { 'UP' } else { 'DOWN' } })
$rows.Add([pscustomobject]@{ 服务 = 'MCP server'; 地址 = "http://127.0.0.1:$McpPort/mcp"; 状态 = if (Test-Port $McpPort) { 'UP' } else { 'DOWN' } })
$rows.Add([pscustomobject]@{ 服务 = 'Worker'; 地址 = '后台轮询（无端口）'; 状态 = if (Get-RecordedPid $workerStem) { 'UP' } else { 'DOWN' } })
if (-not $NoFrontend) {
    $rows.Add([pscustomobject]@{ 服务 = '前端'; 地址 = "http://localhost:$WebPort/"; 状态 = if (Test-Port $WebPort) { 'UP' } else { 'DOWN' } })
}
$rows | Format-Table -AutoSize | Out-String | Write-Host

if ($SkipSeed) {
    Write-Host "演示账号：未写入（-SkipSeed）"
} else {
    Write-Host "演示账号：student_demo / admin_demo    口令：demo1234（仅开发种子）"
}
Write-Host "演示库：$dbName    日志：$LogDir    PID：$RunDir"
Write-Host '停止：.\scripts\stop.ps1        巡检：.\scripts\status.ps1' -ForegroundColor DarkGray
Write-Host '==============================================' -ForegroundColor White

if (-not $healthy) {
    Write-Host ''
    Write-Fail '有后端服务未就绪，请查看日志：'
    Get-ChildItem $LogDir -Filter '*.err.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 0 } |
        ForEach-Object { Write-Host "  --- $($_.Name) ---"; Get-Content $_.FullName -Tail 15 }
    exit 1
}
if (-not $NoFrontend -and -not $webStarted) {
    Write-Fail '前端未能就绪，查看日志：backend\var\logs\web.err.log'
    exit 1
}

exit 0
