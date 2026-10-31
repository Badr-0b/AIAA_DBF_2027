# Battery guard for a detached CFD sweep (Windows PowerShell 5.1).
#
#   Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\Nitro\Documents\GitHub\AIAA_DBF\cfd\tools\battery_guard.ps1','rq4_mock'
#
# Polls the battery every 30 s. When the charge is at or below the threshold (default 10 %) and
# falling (on battery, or dropping despite the charger), it:
#   1. checkpoints and stops the sweep with sweep_stop.sh,
#   2. harvests the results into the repo,
#   3. terminates the Ubuntu WSL distro (every OpenFOAM, ParaView and watcher process),
#   4. kills any remaining Windows process whose command line mentions the AIAA_DBF repo.
# It exits on its own once the sweep is no longer running (finished or stopped by hand).
# Log: cfd/battery_guard.log (gitignored). Resume afterwards with cfd/tools/sweep.sh as usual.
# -DryRun: trigger at once, log what would be stopped and killed, touch nothing.
param([string]$Case = "rq4_mock", [int]$Threshold = 10, [switch]$DryRun)

$Repo = "C:\Users\Nitro\Documents\GitHub\AIAA_DBF"
$Tools = "/mnt/c/Users/Nitro/Documents/GitHub/AIAA_DBF/cfd/tools"
$Log = Join-Path $Repo "cfd\battery_guard.log"

function Say($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Out-File -FilePath $Log -Append -Encoding utf8 }
function SweepRunning {
    @(Get-CimInstance Win32_Process -Filter "Name = 'wsl.exe'" |
      Where-Object { $_.CommandLine -like "*sweep.sh*$Case*" }).Count -gt 0
}

Say "guard started (pid $PID): case $Case, threshold $Threshold %"
$prev = $null
$gone = 0
while ($true) {
    $b = Get-CimInstance Win32_Battery | Select-Object -First 1
    if ($b) {
        $pct = [int]$b.EstimatedChargeRemaining
        $onBattery = @(1, 4, 5) -contains [int]$b.BatteryStatus   # 1 discharging, 4 low, 5 critical
        $falling = $onBattery -or ($null -ne $prev -and $pct -lt $prev)
        if ($DryRun) {
            Say "DRY RUN: battery $pct % (status $($b.BatteryStatus), on battery $onBattery); sweep running: $(SweepRunning)"
            Get-CimInstance Win32_Process |
                Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*AIAA_DBF*" } |
                ForEach-Object { Say "  would kill $($_.Name) (pid $($_.ProcessId))" }
            exit 0
        }
        if ($pct -le $Threshold -and $falling) {
            Say "battery $pct % (status $($b.BatteryStatus)): stopping the sweep"
            & wsl.exe -d Ubuntu -- bash "$Tools/sweep_stop.sh" $Case 2>&1 | ForEach-Object { Say "  stop: $_" }
            & wsl.exe -d Ubuntu -- bash "$Tools/harvest.sh" $Case 2>&1 | Select-Object -Last 2 | ForEach-Object { Say "  harvest: $_" }
            & wsl.exe -t Ubuntu 2>&1 | Out-Null
            Say "  Ubuntu WSL terminated"
            Get-CimInstance Win32_Process |
                Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*AIAA_DBF*" } |
                ForEach-Object {
                    Say "  killing $($_.Name) (pid $($_.ProcessId))"
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                }
            Say "done; resume with cfd/tools/sweep.sh when on AC"
            exit 0
        }
        $prev = $pct
    }
    if (SweepRunning) { $gone = 0 } else { $gone++ }
    if ($gone -ge 4) { Say "sweep no longer running (finished or stopped by hand); guard exiting"; exit 0 }
    Start-Sleep -Seconds 30
}
