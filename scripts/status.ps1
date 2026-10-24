#Requires -Version 7.0

<#
.SYNOPSIS
    校园课程智能助手 · 运行状态巡检（容器 / 数据库 / 四服务 / 前端）

.DESCRIPTION
    只读检查，不改任何状态。用于启动后确认、排障定位、以及汇报环境现状：
      - MySQL 容器是否运行、演示库表数量与迁移版本；
      - 8100/8101/8102/5173 是否监听；
      - 公共 API /api/v1/health 的返回（进程 + 数据库两级）；
      - Worker 进程是否存活、日志末尾是否有错误。

.PARAMETER PublicPort
    公共 API 端口，默认 8100。

.PARAMETER InternalPort
    内部 API 端口，默认 8101。

.PARAMETER McpPort
    MCP server 端口，默认 8102。

.PARAMETER WebPort
    前端 dev server 端口，默认 5173。

.EXAMPLE
    .\scripts\status.ps1
#>
[CmdletBinding()]
param(
    [int]$PublicPort = 8100,
    [int]$InternalPort = 8101,
    [int]$McpPort = 8102,
    [int]$WebPort = 5173
)

$ErrorActionPreference = 'Continue'

$Root      = Split-Path -Parent $PSScriptRoot
$Backend   = Join-Path $Root 'backend'
$RunDir    = Join-Path $Backend 'var\run'
$LogDir    = Join-Path $Backend 'var\logs'
$EnvFile   = Join-Path $Backend '.env'
$Container = 'cca-mysql'
$MysqlRoot = 'cca_dev_root'

function Test-Port([int]$Port) {
    if ($Port -le 0) { return $false }
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# Docker Desktop 的端口转发不一定出现在 Get-NetTCPConnection 里（WSL 中继），
# 所以对容器端口用真实 TCP 连接判断，避免“容器在跑却显示未监听”。
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

function Get-RecordedPid([string]$Name) {
    $file = Join-Path $RunDir "$Name.pid"
    if (-not (Test-Path $file)) { return $null }
    $raw = Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $raw) { return $null }
    $procId = 0
    if (-not [int]::TryParse($raw.Trim(), [ref]$procId)) { return $null }
    if (Get-Process -Id $procId -ErrorAction SilentlyContinue) { return $procId }
    return $null
}

Write-Host ''
Write-Host '校园课程智能助手 · 运行状态' -ForegroundColor White
Write-Host "仓库根：$Root"

# ---- 配置 ---------------------------------------------------------------- #
$dbUrl  = Get-EnvValue $EnvFile 'DATABASE_URL'
$dbName = if ($dbUrl) { ($dbUrl -split '/')[-1].Split('?')[0] } else { '<未配置>' }
Write-Host ''
Write-Host "配置：backend/.env $(if (Test-Path $EnvFile) { '存在' } else { '缺失（start.ps1 会生成）' })    库：$dbName"

# ---- MySQL --------------------------------------------------------------- #
$mysqlRows = New-Object System.Collections.Generic.List[object]
docker inspect $Container --format '{{.State.Running}}' 2>$null | Out-Null
$containerState = if ($LASTEXITCODE -eq 0) { (docker inspect $Container --format '{{.State.Status}}  {{.State.StartedAt}}').Trim() } else { '不存在' }
$mysqlRows.Add([pscustomobject]@{ 项 = '容器'; 值 = "$Container : $containerState" })

if (Test-TcpConnect '127.0.0.1' 33061) {
    $tables = (& docker exec $Container mysql -uroot "-p$MysqlRoot" -N -e `
        "select count(*) from information_schema.tables where table_schema='$dbName';" 2>$null)
    $rev = (& docker exec $Container mysql -uroot "-p$MysqlRoot" -N -e `
        "select version_num from $dbName.alembic_version;" 2>$null)
    $users = (& docker exec $Container mysql -uroot "-p$MysqlRoot" -N -e `
        "select count(*) from $dbName.users;" 2>$null)
    $mysqlRows.Add([pscustomobject]@{ 项 = '33061'; 值 = '监听中' })
    $mysqlRows.Add([pscustomobject]@{ 项 = "$dbName 表数"; 值 = "$(($tables | Select-Object -First 1))" })
    $mysqlRows.Add([pscustomobject]@{ 项 = '迁移版本'; 值 = "$(($rev | Select-Object -First 1))" })
    $mysqlRows.Add([pscustomobject]@{ 项 = '用户数'; 值 = "$(($users | Select-Object -First 1))" })
} else {
    $mysqlRows.Add([pscustomobject]@{ 项 = '33061'; 值 = '未监听' })
}
$mysqlRows | Format-Table -AutoSize | Out-String | Write-Host

# ---- 服务 ---------------------------------------------------------------- #
$healthStatus = '-'
$healthDetail = '-'
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$PublicPort/api/v1/health" -TimeoutSec 3 -ErrorAction Stop
    $healthStatus = $health.data.status
    $healthDetail = "process=$($health.data.checks.process) database=$($health.data.checks.database)"
} catch {
    $healthStatus = 'unreachable'
}

# 前端：默认实例（8100）探 5173；非默认实例没有固定前端端口，
# 只按 web-<公共端口>.pid 判断，避免把默认实例的 5173 算到别的实例头上。
if ($PublicPort -eq 8100) {
    $frontendPort = $WebPort
    $frontendState = if (Test-Port $frontendPort) { 'UP' } else { 'DOWN' }
    $webStatus = if (Test-Port $frontendPort) {
        try {
            # Vite 默认只绑 localhost（本机解析到 ::1），不能用 127.0.0.1 探活。
            $r = Invoke-WebRequest -Uri "http://localhost:$frontendPort/" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            "HTTP $($r.StatusCode)"
        } catch { '监听但无响应' }
    } else { '未监听' }
} else {
    $frontendPort = '-'
    $webPid = Get-RecordedPid "web-$PublicPort"
    $frontendState = if ($webPid) { 'UP' } else { 'DOWN' }
    $webStatus = if ($webPid) { "PID $webPid（非默认实例，端口由启动参数决定）" } else { '该实例未起前端' }
}

$workerStem = if ($PublicPort -eq 8100) { 'worker' } else { "worker-$PublicPort" }
$workerPid = Get-RecordedPid $workerStem
$svcRows = @(
    [pscustomobject]@{ 服务 = '公共 API'; 端口 = $PublicPort; 状态 = if (Test-Port $PublicPort) { 'UP' } else { 'DOWN' }; 附加 = "health=$healthStatus（$healthDetail）" },
    [pscustomobject]@{ 服务 = '内部 API'; 端口 = $InternalPort; 状态 = if (Test-Port $InternalPort) { 'UP' } else { 'DOWN' }; 附加 = '只回环' },
    [pscustomobject]@{ 服务 = 'MCP server'; 端口 = $McpPort; 状态 = if (Test-Port $McpPort) { 'UP' } else { 'DOWN' }; 附加 = '私有 Streamable HTTP' },
    [pscustomobject]@{ 服务 = 'Worker'; 端口 = '-'; 状态 = if ($workerPid) { 'UP' } else { 'DOWN' }; 附加 = if ($workerPid) { "PID $workerPid" } else { '无 PID 记录' } },
    [pscustomobject]@{ 服务 = '前端'; 端口 = $frontendPort; 状态 = $frontendState; 附加 = $webStatus }
)
$svcRows | Format-Table -AutoSize | Out-String | Write-Host

# ---- 日志里的错误级输出 -------------------------------------------------- #
# uvicorn 把 INFO 启动日志写到 stderr，所以 *.err.log 非空不代表故障；
# 这里只挑 ERROR / Traceback / Exception / CRITICAL 行，避免健康状态下刷屏。
if (Test-Path $LogDir) {
    $errLogs = Get-ChildItem $LogDir -Filter '*.err.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 0 }
    $hits = @()
    foreach ($f in $errLogs) {
        $lines = Get-Content $f.FullName -Tail 300 -ErrorAction SilentlyContinue |
            Where-Object { $_ -match 'ERROR|CRITICAL|Traceback|Exception|FAILED' }
        if ($lines) {
            $hits += [pscustomobject]@{ Name = $f.Name; Lines = @($lines | Select-Object -Last 5) }
        }
    }
    if ($hits.Count -gt 0) {
        Write-Host '日志中的错误行（每条日志最近 5 行）：' -ForegroundColor Yellow
        foreach ($h in $hits) {
            Write-Host "  --- $($h.Name) ---" -ForegroundColor DarkGray
            $h.Lines | ForEach-Object { Write-Host "  $_" }
        }
    } else {
        Write-Host '日志：无 ERROR/Traceback（仅有 INFO 级启动日志）' -ForegroundColor DarkGray
    }
}

$down = @($svcRows | Where-Object { $_.状态 -eq 'DOWN' })
Write-Host ''
if ($down.Count -eq 0) {
    Write-Host '全部服务 UP' -ForegroundColor Green
} else {
    Write-Host ("未运行：" + (($down | ForEach-Object { $_.服务 }) -join '，') + "    启动：.\scripts\start.ps1") -ForegroundColor Yellow
}
Write-Host "日志目录：$LogDir" -ForegroundColor DarkGray

exit 0
