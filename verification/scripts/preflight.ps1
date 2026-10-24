<#
  preflight.ps1 -- read-only environment preflight for Phase 5 independent verification.
  Verifies isolation, toolchain, DB reachability and the freeze anchors. Writes nothing
  outside verification/.

  Usage: pwsh -NoProfile -File verification/scripts/preflight.ps1
#>
$ErrorActionPreference = 'Continue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$Py        = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Backend   = Join-Path $RepoRoot 'backend'
$fail = 0
function Check([string]$Name, [scriptblock]$Body) {
  try {
    $result = & $Body
    Write-Output ("PASS  " + $Name + " :: " + $result)
  } catch {
    $script:fail += 1
    Write-Output ("FAIL  " + $Name + " :: " + $_.Exception.Message)
  }
}

Write-Output '=== git / freeze anchor ==='
Check 'git branch = dev' { (git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim() }
Check 'git HEAD sha' { (git -C $RepoRoot rev-parse HEAD).Trim() }
Check 'git working tree clean outside verification/ (0 entries)' {
  $entries = @(git -C $RepoRoot status --porcelain | Where-Object { $_ -notmatch '^\?\?\s+verification/' })
  if ($entries.Count -gt 0) { throw ("dirty: " + ($entries -join ' | ')) }
  # verification/ is the verifier's write scope and stays untracked until the Lead commits/rejects it.
  $all = @(git -C $RepoRoot status --porcelain)
  "ok (untracked in verification/: $($all.Count))"
}
Write-Output ('INFO  HEAD ' + (git -C $RepoRoot log -1 --format='%h %s'))

Write-Output '=== toolchain ==='
Check 'python <root>/.venv' { (& $Py -c "import sys;print(sys.version.split()[0])") }
Check 'pytest version' { (& $Py -m pytest --version 2>&1 | Select-Object -First 1) }
Check 'alembic version' { (& $Py -m alembic --version 2>&1 | Select-Object -Last 1) }
Check 'node version' { (node --version) }
Check 'pnpm version' { (pnpm --version) }
Check 'web/node_modules present' { if (Test-Path (Join-Path $RepoRoot 'web\node_modules')) { 'yes' } else { throw 'missing web/node_modules' } }

Write-Output '=== mysql container / databases ==='
Check 'container cca-mysql running' { (docker inspect -f '{{.State.Status}}' cca-mysql) }
Check 'cca_test_release exists' {
  $db = docker exec cca-mysql mysql -uroot -pcca_dev_root -N -e "SHOW DATABASES LIKE 'cca_test_release';" 2>$null
  if (($db | Out-String).Trim() -ne 'cca_test_release') { throw 'missing cca_test_release' }
  'yes'
}
Check 'cca_test_release table count (incl. alembic_version)' {
  $n = docker exec cca-mysql mysql -uroot -pcca_dev_root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='cca_test_release';" 2>$null
  ($n | Select-Object -Last 1).ToString().Trim()
}
Check 'mysql server version' {
  $v = docker exec cca-mysql mysql -uroot -pcca_dev_root -N -e "SELECT VERSION();" 2>$null
  ($v | Select-Object -Last 1).ToString().Trim()
}

Write-Output '=== isolation: my ports free / lead ports in use ==='
foreach ($p in 8200, 8201, 8202, 5273) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { Write-Output "WARN  port $p already in use pid=$($c[0].OwningProcess) (must be mine or free)" }
  else { Write-Output "PASS  port $p free" }
}
foreach ($p in 8100, 8101, 8102, 5173) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { Write-Output "INFO  lead port $p listening pid=$($c[0].OwningProcess) (must not be touched)" }
  else { Write-Output "INFO  lead port $p not listening" }
}

Write-Output '=== contract freeze anchors (docs are disk truth, not in git) ==='
$anchors = @(
  'docs/backend/openapi_v0.1.json',
  'docs/backend/mcp_tools_v0.1.json',
  'docs/backend/sse_events_v0.1.schema.json',
  'docs/backend/cca_schema_v0.1.sql'
)
foreach ($rel in $anchors) {
  $path = Join-Path $RepoRoot $rel
  if (-not (Test-Path $path)) { Write-Output "FAIL  missing $rel"; $fail += 1; continue }
  $hash = (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLower()
  $len  = (Get-Item $path).Length
  Write-Output ('ANCHOR ' + $hash + ' ' + $len + ' ' + $rel)
}

Write-Output '=== source tree raw counts (independent baseline) ==='
Check 'backend test files' { @(Get-ChildItem (Join-Path $Backend 'tests') -Filter 'test_*.py').Count }
Check 'backend test functions (grep def test_)' {
  (Select-String -Path (Join-Path $Backend 'tests\test_*.py') -Pattern '^\s*(async )?def test_' -AllMatches).Count
}
Check 'alembic migrations' { @(Get-ChildItem (Join-Path $Backend 'migrations\versions') -Filter '*.py').Count }

Write-Output ''
if ($fail -gt 0) { Write-Output ("PREFLIGHT RESULT: FAIL ($fail)"); exit 1 }
Write-Output 'PREFLIGHT RESULT: PASS'
exit 0
