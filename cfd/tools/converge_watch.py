# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Stop a running foamRun once its force history is flat (the WP-01 rule, report_case.flat).

    python3 cfd/tools/converge_watch.py <run dir> <min iterations>    (Allrun starts it beside foamRun)

Every CONV_POLL s (default 30) it reads postProcessing/coeffs/*/forceCoeffs.dat. With at least
<min iterations> and two full windows of CONV_WINDOW iterations (default 200), it asks for a
write-and-stop when the means of C_L and C_D have not moved by more than the WP-01 tolerance
since the window before (no slow drift) and their spread over the last window is within
CONV_SPREAD (default 2) times that tolerance. A steady oscillation (a flapping laminar bubble,
say) does not shrink with more iterations, so running on buys nothing; report_case.py still
marks such a run CHECK against the WP-01 spread limit. CONV_TOL scales both tolerances
(default 1; large values only to test the pipeline). The stop is `stopAt writeNow` in
system/controlDict (runTimeModifiable); Allrun sets it back to endTime for the next angle.
"""
import os
import re
import sys
import time
from pathlib import Path

from report_case import coeffs, flat

RUN = Path(sys.argv[1]).resolve()
NMIN = int(sys.argv[2])
W = int(os.environ.get("CONV_WINDOW", 200))
POLL = float(os.environ.get("CONV_POLL", 30))
TOL = float(os.environ.get("CONV_TOL", 1))
SPREAD = float(os.environ.get("CONV_SPREAD", 2))
print(f"watching {RUN}: min {NMIN} iterations, window {W}, tolerance x{TOL:g}, spread x{SPREAD:g}",
      flush=True)

while True:
    time.sleep(POLL)
    try:
        c = coeffs(RUN, "coeffs")
    except (ValueError, IndexError):  # last line still being written
        continue
    if c is None or len(c["Time"]) < max(NMIN, 2 * W):
        continue
    _, m, sp, tol = flat(c, W)
    drift = {k: abs(m[k] - c[k][-2 * W:-W].mean()) for k in tol}
    ok = all(sp[k] <= SPREAD * TOL * tol[k] and drift[k] <= TOL * tol[k] for k in tol)
    it = c["Time"][-1]
    print(f"{it:.0f}: CL {m['Cl']:.5f} spread {sp['Cl']:.2g} drift {drift['Cl']:.2g} | "
          f"CD {m['Cd']:.6f} spread {sp['Cd']:.2g} drift {drift['Cd']:.2g} | drift tol {TOL * tol['Cl']:.2g}, "
          f"{TOL * tol['Cd']:.2g}, spread x{SPREAD:g} -> {'flat' if ok else 'not yet'}", flush=True)
    if ok:
        cd = RUN / "system" / "controlDict"
        cd.write_text(re.sub(r"^stopAt\s+\w+;", "stopAt          writeNow;", cd.read_text(), flags=re.M))
        print(f"flat at iteration {it:.0f}: stopAt writeNow", flush=True)
        break
