# Session battery guard for the DB-02 Claude Code session (written 30 Oct 2026, at the user's request).
#
# Every 60 s it checks the battery. When the battery is at or below the threshold AND the laptop is
# on battery (not charging), it:
#   1. writes DB-02_aircraft_variants\ledger\BATTERY_STOP.flag (the session checks for it and stops cleanly);
#   2. snapshots the work folder (code, report sources, ledger, memos, results; no CFD meshes, raw downloads
#      or build files) into DB-02_aircraft_variants\checkpoints\DB02_<time>.zip  (NOT committed; git untouched);
#   3. waits a 90 s grace period (aborts everything if the charger is plugged in meanwhile);
#   4. stops Python jobs running from the DB-02 folder, then ends the Claude Code process given by -ClaudePid.
# Resume later with:  claude -c   (the conversation transcript is kept by Claude Code).
#
# Start detached (PowerShell):
#   Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
#     'C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants\tools\session_guard.ps1','-ClaudePid','<pid>'
# Stop the guard:  delete tools\session_guard.run  (it exits within 60 s)
param(
  [int]$ClaudePid,
  [int]$Threshold = 10,
  [int]$GraceSeconds = 90,
  [int]$PollSeconds = 60,
  [switch]$DryRun
)
$ErrorActionPreference = 'Continue'
$W = 'C:\Users\Nitro\Documents\GitHub\AIAA_DBF\DB-02_aircraft_variants'
$Log = Join-Path $W 'tools\session_guard.log'
$Run = Join-Path $W 'tools\session_guard.run'
$Flag = Join-Path $W 'ledger\BATTERY_STOP.flag'
function Log($m) { "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m | Add-Content -Path $Log -Encoding utf8 }
function Battery {
  $b = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1
  $pct = (Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1).EstimatedChargeRemaining
  [pscustomobject]@{ Pct = [int]$pct; OnAC = [bool]$b.PowerOnline; Charging = [bool]$b.Charging }
}
function Snapshot {
  $ts = Get-Date -Format 'yyyyMMdd_HHmm'
  $dir = Join-Path $W 'checkpoints'; New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $stage = Join-Path $env:TEMP "db02_snap_$ts"
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  foreach ($sub in 'brief','early','ledger','memos','src','tests','sources','tools','report') {
    $s = Join-Path $W $sub
    if (Test-Path $s) { robocopy $s (Join-Path $stage $sub) /E /XD build specimens __pycache__ ref_renders /XF *.pyc *.zip /NFL /NDL /NJH /NJS /NP | Out-Null }
  }
  $o = Join-Path $W 'out'
  if (Test-Path $o) { robocopy $o (Join-Path $stage 'out') *.json *.csv *.md *.log /S /XD raw work screen_rows /NFL /NDL /NJH /NJS /NP | Out-Null }
  $zip = Join-Path $dir "DB02_$ts.zip"
  Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
  Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
  $recent = Get-ChildItem -Path $W -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-3) -and $_.FullName -notmatch '\\(checkpoints|build|work|raw|specimens)\\' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 60
  $md = @("# Battery checkpoint $ts", "", "Snapshot: $zip (not committed).", "Resume: claude -c", "",
          "Files changed in the last 3 h (newest first):") + ($recent | ForEach-Object { "- " + $_.FullName.Substring($W.Length + 1) + "  (" + $_.LastWriteTime.ToString('HH:mm') + ")" })
  Set-Content -Path (Join-Path $W "ledger\CHECKPOINT_$ts.md") -Value $md -Encoding utf8
  return $zip
}

Set-Content -Path $Run -Value $PID -Encoding ascii
Log "guard started (pid $PID), claude pid $ClaudePid, threshold $Threshold %, dry run $DryRun"
while ($true) {
  if (-not (Test-Path $Run)) { Log 'run file removed: guard exits'; break }
  if ($ClaudePid -and -not (Get-Process -Id $ClaudePid -ErrorAction SilentlyContinue)) { Log "claude pid $ClaudePid gone: guard exits"; break }
  $b = Battery
  if ($DryRun) { Log ("DRY RUN: battery {0} %, AC {1}, charging {2}" -f $b.Pct, $b.OnAC, $b.Charging) }
  if ($b.Pct -le $Threshold -and -not $b.OnAC) {
    Log ("battery {0} % on battery: stopping the session" -f $b.Pct)
    Set-Content -Path $Flag -Value ("battery {0} % at {1}; session being stopped by tools\session_guard.ps1; resume with: claude -c" -f $b.Pct, (Get-Date)) -Encoding utf8
    try { $z = Snapshot; Log "snapshot $z" } catch { Log "snapshot failed: $_" }
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $GraceSeconds) {
      Start-Sleep -Seconds 10
      if ((Battery).OnAC) { Log 'charger connected during grace: aborting the stop'; Remove-Item $Flag -ErrorAction SilentlyContinue; break }
    }
    if ((Battery).OnAC) { Start-Sleep -Seconds $PollSeconds; continue }
    if ($DryRun) { Log 'DRY RUN: would stop python jobs and claude now'; break }
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'DB-02_aircraft_variants' } |
      ForEach-Object { Log ("stopping python {0}" -f $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($ClaudePid) { Log "ending claude pid $ClaudePid (resume with: claude -c)"; taskkill /PID $ClaudePid /T /F | Out-Null }
    Remove-Item $Run -ErrorAction SilentlyContinue
    Log 'session stopped; guard exits'
    break
  }
  Start-Sleep -Seconds $PollSeconds
}
