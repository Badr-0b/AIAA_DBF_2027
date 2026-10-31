# Copyright © 2026 Badr Obtel. All rights reserved.
"""Headless XFoil 6.99 driver: lift sweeps with an optional plain flap (TOOLING).

Method follows the team's airfoil study (dbf_airfoil_study/scripts/xfoil_driver.py,
11 Oct 2026):
- the LOAD -> GDES/CADD -> PANE load sequence and the 240-panel repanel;
- one XFoil process per sweep in its own temporary directory, graphics off;
- a process silent for 30 s is killed (the boundary-layer solver can hang);
- a sweep that diverges before stall is restarted from a fresh boundary-layer
  initialisation one step past the last converged angle.
Added here: GDES FLAP (hinge x/c, hinge y as a fraction of the local thickness,
deflection + down), applied before repanelling, and no pandas dependency.

XFoil is a 2-D panel method with a coupled integral boundary layer, not CFD.
"""
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = (os.environ.get("XFOIL_EXE") or shutil.which("xfoil") or shutil.which("xfoil.exe")
       or str(HERE / "tools" / "xfoil.exe"))
N_PANELS = 240
NCRIT = 9.0
ITER = 100
IDLE_S = 30
STALL_DROP = 0.05      # stall captured: CL fallen this far below its peak ...
STALL_MARGIN = 1.0     # ... at least this many degrees past the peak
MAX_RESTARTS = 6


def _run(cmds, cwd, timeout=240):
    proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, cwd=cwd)
    proc.stdin.write(("\n".join(cmds) + "\n").encode())
    proc.stdin.close()
    chunks, last = [], [time.time()]

    def reader():
        while True:
            b = proc.stdout.read1(65536)
            if not b:
                break
            chunks.append(b)
            last[0] = time.time()

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    t0 = time.time()
    while proc.poll() is None:
        now = time.time()
        if now - t0 > timeout or now - last[0] > IDLE_S:
            proc.kill()
            break
        time.sleep(0.1)
    proc.wait()
    th.join(5)
    return b"".join(chunks).decode(errors="ignore")


def _polar(path):
    """(alpha, CL, CD, CM) rows of an XFoil PACC file, sorted by alpha."""
    rows, started = {}, False
    if not path.exists():
        return []
    for ln in path.read_text().splitlines():
        if ln.strip().startswith("------"):
            started = True
            continue
        if started and ln.strip():
            try:
                v = [float(x) for x in ln.split()]
            except ValueError:
                continue
            if len(v) >= 5:
                rows[v[0]] = (v[0], v[1], v[2], v[4])
    return [rows[a] for a in sorted(rows)]


def sweep_once(dat, re, a0, a1, step, flap=None, ncrit=NCRIT):
    """One ASEQ sweep from a fresh boundary-layer initialisation.

    flap  None, or (hinge_x_c, hinge_y_over_t, deflection_deg); y/t 0 = lower
          surface, 0.5 = mid-thickness, 1 = upper surface.
    """
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        shutil.copy(dat, td / "af.dat")
        cmds = ["PLOP", "G F", "", "LOAD af.dat", "GDES", "CADD", "", "", ""]   # 3 CADD prompts
        if flap:
            x, yt, d = flap
            cmds += ["FLAP", f"{x:g}", "999", f"{yt:g}", f"{d:g}", "EXEC"]
        cmds += ["", "PANE", "PPAR", f"N {N_PANELS}", "", "",                  # "" leaves GDES
                 "OPER", "VPAR", f"N {ncrit:g}", "", f"VISC {re:.0f}", "MACH 0", f"ITER {ITER}",
                 "PACC", "polar.txt", "", f"ASEQ {a0:g} {a1:g} {step:g}", "", "QUIT"]
        _run(cmds, td)
        return _polar(td / "polar.txt")


def _stalled(rows, a1):
    if not rows:
        return False
    if rows[-1][0] >= a1 - 1e-6:
        return True
    ipk = max(range(len(rows)), key=lambda i: rows[i][1])
    return rows[ipk][0] <= rows[-1][0] - STALL_MARGIN and rows[-1][1] <= rows[ipk][1] - STALL_DROP


def sweep_up(dat, re, a0=-4.0, a1=22.0, step=0.25, flap=None, ncrit=NCRIT):
    """Up-sweep to stall with the restart rule. Returns rows and restart angles."""
    rows = sweep_once(dat, re, a0, a1, step, flap, ncrit)
    starts, start = [], a0
    while not _stalled(rows, a1) and len(starts) < MAX_RESTARTS:
        reached = rows[-1][0] if rows else a0 - step
        nxt = reached + step
        if nxt <= start:
            nxt = start + 1.0
        if nxt > a1:
            break
        start = round(nxt, 4)
        starts.append(start)
        more = sweep_once(dat, re, start, a1, step, flap, ncrit)
        merged = {r[0]: r for r in rows}
        for r in more:
            merged.setdefault(r[0], r)
        rows = [merged[a] for a in sorted(merged)]
    return rows, starts


def clmax(rows):
    """(CLmax, alpha at CLmax, stall_captured) of an up-sweep. stall_captured is
    False when the sweep ended without CL falling past its peak (non-convergence
    near stall), in which case CLmax is a lower bound of XFoil's own prediction."""
    if not rows:
        return float("nan"), float("nan"), False
    ipk = max(range(len(rows)), key=lambda i: rows[i][1])
    cap = rows[ipk][0] <= rows[-1][0] - STALL_MARGIN and rows[-1][1] <= rows[ipk][1] - STALL_DROP
    return rows[ipk][1], rows[ipk][0], cap
