"""S2 runner: calibration, back-test, density, charts and results.json (writes only W/out/field).

    set PYTHONDONTWRITEBYTECODE=1 & python -m field.run_s2 <step>     (cwd = W/src)

Steps: calibrate | backtest | density | reliability | results | all
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from . import model as fm
from . import calibrate as cal

OUT = fm.W / "out" / "field"


def step_calibrate():
    from scipy.optimize import minimize
    obs = cal.observed_moments()
    names = ("lam_report", "lam_tech", "lam_flight", "lam_gm", "lam_value", "rho_m2m3")
    x0 = np.array([fm.PARAMS[k] for k in names])
    log = []

    def f(x):
        if np.any(x <= 0.0) or np.any(x >= 0.97):
            return 10.0
        p = dict(zip(names, x))
        if p["rho_m2m3"] >= 0.95:
            return 10.0
        e, _ = cal.loss(p, obs, n=100, seed=11)
        log.append((e, *x))
        return e

    t = time.time()
    res = minimize(f, x0, method="Nelder-Mead", options={"maxfev": 140, "xatol": 0.01, "fatol": 1e-4})
    best = dict(zip(names, [float(v) for v in res.x]))
    e, sims = cal.loss(best, obs, n=300, seed=99)
    rep = {"params": best, "loss": e, "evals": len(log), "seconds": time.time() - t,
           "observed_pooled": {k: float(np.nanmean([obs[y][k] for y in fm.YEARS_P])) for k in cal.MOMENT_KEYS},
           "simulated_pooled": {k: float(np.nanmean([sims[y][k] for y in fm.YEARS_P])) for k in cal.MOMENT_KEYS},
           "observed": obs, "simulated": sims}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration.json").write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("params", "loss", "evals", "seconds", "observed_pooled",
                                          "simulated_pooled")}, indent=1, default=float))


if __name__ == "__main__":
    steps = sys.argv[1:] or ["all"]
    for s in steps:
        globals()[f"step_{s}"]()
