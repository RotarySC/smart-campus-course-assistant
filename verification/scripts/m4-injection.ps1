<#
  m4-injection.ps1 -- execute verification/scripts/m4-injection.sql probes against cca_test_release.

  Each probe is expected to be REJECTED by MySQL itself (CHECK 3819 / unique 1062 / FK 1452 /
  length 1406...). A probe that succeeds is a FAIL (constraint missing). A control INSERT must
  succeed, proving the session is not simply read-only.

  The database name is hard-coded to cca_test_release; this script refuses anything else.
#>
param([string]$Database = 'cca_test_release')

$ErrorActionPreference = 'Continue'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$SqlFile   = Join-Path $ScriptDir 'm4-injection.sql'
$Container = 'cca-mysql'
$RootPwd   = 'cca_dev_root'

if ($Database -ne 'cca_test_release') {
  throw "refusing to run: this probe file is only allowed against cca_test_release (got '$Database')"
}

$expected = @{
  1  = @{ Code = 3819; Constraint = 'ck_users_role' }
  2  = @{ Code = 3819; Constraint = 'ck_users_names' }
  3  = @{ Code = 1062; Constraint = 'uq_users_account' }
  4  = @{ Code = 3819; Constraint = 'ck_sessions_expiry' }
  5  = @{ Code = 3819; Constraint = 'ck_schedule_times' }
  6  = @{ Code = 3819; Constraint = 'ck_chat_state' }
  7  = @{ Code = 3819; Constraint = 'ck_chat_terminal' }
  8  = @{ Code = 1062; Constraint = 'uq_document_one_active' }
  9  = @{ Code = 3819; Constraint = 'ck_chunk_text' }
  10 = @{ Code = 3819; Constraint = 'ck_corpus_singleton' }
  11 = @{ Code = 3819; Constraint = 'ck_document_removed' }
  12 = @{ Code = 1452; Constraint = 'fk_chunk_document' }
}

function Invoke-Sql([string]$Text) {
  # NB: use "--password=<v>" (a single native argument). PowerShell mis-passes the combined
  # form "-p$v" to native commands in this host, which yields ERROR 1045.
  $out = $Text | docker exec -i $Container mysql -uroot "--password=$RootPwd" $Database 2>&1
  return @{ Exit = $LASTEXITCODE; Out = ($out | Out-String) }
}

$lines = Get-Content -Path $SqlFile
$segments = [ordered]@{}
$current = $null
foreach ($line in $lines) {
  # marker lines may carry a trailing description: "-- @probe 1  ck_users_role：..."
  if ($line -match '^--\s*@(setup|control|teardown|probe\s+(\d+))\b') {
    if ($Matches[2]) { $current = 'probe' + $Matches[2] } else { $current = $Matches[1] }
    $segments[$current] = New-Object System.Collections.Generic.List[string]
    continue
  }
  if ($current) { $segments[$current].Add($line) }
}

$fail = 0
$failures = @()

# --- setup ---
$setup = ($segments['setup'] -join "`n")
$r = Invoke-Sql $setup
if ($r.Exit -ne 0) {
  Write-Output "SETUP FAILED (exit $($r.Exit)):`n$($r.Out)"
  exit 1
}
Write-Output 'SETUP ok (parent rows inserted: user/session/conversation/course/batch/document/version; corpus_control reset)'

# --- probes ---
foreach ($n in 1..12) {
  $key = 'probe' + $n
  if (-not $segments.Contains($key)) { Write-Output "PROBE $n MISSING"; $fail++; continue }
  $sql = ($segments[$key] -join "`n")
  $r = Invoke-Sql $sql
  $codeMatch = [regex]::Match($r.Out, 'ERROR (\d+)')
  $code = if ($codeMatch.Success) { [int]$codeMatch.Groups[1].Value } else { 0 }
  $exp = $expected[$n]
  if ($r.Exit -eq 0) {
    Write-Output ("PROBE {0,2} FAIL  expected reject ({1} / {2}) but INSERT SUCCEEDED" -f $n, $exp.Code, $exp.Constraint)
    $fail++; $failures += "probe$n succeeded"
  } elseif ($code -eq $exp.Code) {
    Write-Output ("PROBE {0,2} PASS  rejected by MySQL errno={1} ({2})" -f $n, $code, $exp.Constraint)
  } else {
    Write-Output ("PROBE {0,2} FAIL  rejected with errno={1}, expected {2} ({3}) :: {4}" -f $n, $code, $exp.Code, $exp.Constraint, ($r.Out.Trim() -replace '\s+', ' '))
    $fail++; $failures += "probe$n errno=$code"
  }
}

# --- control ---
$control = ($segments['control'] -join "`n")
$r = Invoke-Sql $control
if ($r.Exit -eq 0) {
  Write-Output 'CONTROL PASS  legal INSERT accepted (schedule 08:00-09:00)'
} else {
  Write-Output "CONTROL FAIL (exit $($r.Exit)): $($r.Out.Trim() -replace '\s+', ' ')"
  $fail++; $failures += 'control insert rejected'
}

# --- teardown ---
$teardown = ($segments['teardown'] -join "`n")
$r = Invoke-Sql $teardown
if ($r.Exit -ne 0) { Write-Output "TEARDOWN warning (exit $($r.Exit)): $($r.Out.Trim() -replace '\s+', ' ')" }

Write-Output ''
if ($fail -gt 0) { Write-Output ("M4 INJECTION RESULT: FAIL ({0}) :: {1}" -f $fail, ($failures -join '; ')); exit 1 }
Write-Output 'M4 INJECTION RESULT: PASS (12/12 bad rows rejected, 1/1 control accepted)'
exit 0
