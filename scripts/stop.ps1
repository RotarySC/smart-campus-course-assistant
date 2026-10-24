#Requires -Version 7.0

<#
.SYNOPSIS
    校园课程智能助手 · 停止脚本（停后端四服务 + 前端；可选停 MySQL 容器）

.DESCRIPTION
    与 scripts/start.ps1 配对使用：
      - 先按 backend/var/run/*.pid 结束记录的进程；
      - 再按端口兜底结束监听进程（pnpm / uvicorn 可能留下子进程）；
      - 删除 PID 文件并确认端口已释放。
    MySQL 容器默认**不停**（--restart unless-stopped，停了下次启动要等初始化），
    需要一起停用 -StopDocker。

.PARAMETER PublicPort
    公共 API 端口，默认 8100（需与 scripts/start.ps1 启动时一致）。

.PARAMETER InternalPort
    内部 API 端口，默认 8101。

.PARAMETER McpPort
    MCP server 端口，默认 8102。

.PARAMETER WebPort
    前端 dev server 端口，默认 5173。

.PARAMETER StopDocker
    同时停止 MySQL 容器 cca-mysql（数据保留在容器卷中）。

.EXAMPLE
    .\scripts\stop.ps1
    停全部应用进程，保留数据库。

.EXAMPLE
    .\scripts\stop.ps1 -StopDocker
    连 MySQL 容器一起停（收工）。
#>
[CmdletBinding()]
param(
    [int]$PublicPort = 8100,
    [int]$InternalPort = 8101,
    [int]$McpPort = 8102,
    [int]$WebPort = 5173,
    [switch]$StopDocker
)

$ErrorActionPreference = 'Continue'

$Root      = Split-Path -Parent $PSScriptRoot
$Backend   = Join-Path $Root 'backend'
$RunDir    = Join-Path $Backend 'var\run'
$Container = 'cca-mysql'

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text)   { Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text){ Write-Host "  [WARN] $Text" -ForegroundColor Yellow }

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

# 非默认端口时 PID 名带端口后缀（与 start.ps1 的 Get-InstanceStem 保持一致），
# 这样停 8200 那套不会误删 8100 那套的 PID 记录。
function Get-InstanceStem([string]$Name, [int]$Port, [int]$DefaultPort) {
    if ($Port -gt 0 -and $Port -ne $DefaultPort) { return "$Name-$Port" }
    return $Name
}

function Stop-One([string]$Name, [string]$Label, [int]$Port, [int]$DefaultPort = 0) {
    $stem = Get-InstanceStem $Name $Port $DefaultPort
    $killed = @()
    $procId = Get-RecordedPid $stem
    if ($procId) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        $killed += "PID $procId"
    }
    if ($Port -gt 0) {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            if ($conn.OwningProcess -and $conn.OwningProcess -ne 0) {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                $killed += "端口 $Port 的 PID $($conn.OwningProcess)"
            }
        }
    }
    Remove-Item (Join-Path $RunDir "$stem.pid") -ErrorAction SilentlyContinue

    if ($killed.Count -gt 0) {
        Write-Ok "$Label 已停止（$($killed -join '，')）"
    } else {
        Write-Warn2 "$Label 未在运行"
    }
}

Write-Host ''
Write-Host '校园课程智能助手 · 停止服务' -ForegroundColor White

Write-Step '1/2 停止应用进程（前端 → worker → mcp → internal → public）'
# 前端/Worker 没有自己的对外端口，按公共 API 端口区分实例：
# 默认实例（8100）用 web / worker，其他实例用 web-<公共端口> / worker-<公共端口>。
# 非默认实例**不按 5173 兜底**——那个端口可能是默认实例的，误杀会打断别人的会话。
$webStem    = if ($PublicPort -eq 8100) { 'web' }    else { "web-$PublicPort" }
# 注意：变量名不要写成 $webPort —— PowerShell 变量名不区分大小写，会与 -WebPort 参数冲突。
$frontendPort = if ($PublicPort -eq 8100) { $WebPort } else { 0 }
$workerStem = if ($PublicPort -eq 8100) { 'worker' } else { "worker-$PublicPort" }
Stop-One $webStem    '前端 dev server' $frontendPort 5173
Stop-One $workerStem '文档 Worker'     0
Stop-One 'mcp'      'MCP server'      $McpPort      8102
Stop-One 'internal' '内部 API'        $InternalPort 8101
Stop-One 'public'   '公共 API'        $PublicPort   8100

Start-Sleep -Milliseconds 600

Write-Step '2/2 端口确认'
$left = @()
$checked = @()
$ports = @(
    @{Port=$PublicPort;   Name='公共 API'},
    @{Port=$InternalPort; Name='内部 API'},
    @{Port=$McpPort;      Name='MCP server'}
)
# 非默认实例不认领 5173：那个端口可能属于默认实例，不应报「仍被占用」误导。
if ($PublicPort -eq 8100) { $ports += @{Port=$WebPort; Name='前端'} }
foreach ($p in $ports) {
    $checked += "$($p.Port)"
    if (Get-NetTCPConnection -LocalPort $p.Port -State Listen -ErrorAction SilentlyContinue) {
        $left += "$($p.Name) $($p.Port)"
    }
}
if ($left.Count -eq 0) {
    Write-Ok ("$($checked -join '/') 已全部释放")
} else {
    Write-Warn2 ("仍被占用：" + ($left -join '，') + "（可能是不属于本项目的进程，按需手工处理）")
}

if ($StopDocker) {
    Write-Step '额外：停止 MySQL 容器'
    & docker stop $Container | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "容器已停止：$Container（数据保留）" }
    else { Write-Warn2 "容器 $Container 停止失败或不存在" }
} else {
    Write-Host ''
    Write-Host "MySQL 容器 $Container 保持运行（如需停止：.\scripts\stop.ps1 -StopDocker）" -ForegroundColor DarkGray
}

exit 0
