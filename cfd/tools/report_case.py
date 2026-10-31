# Copyright © 2026 Badr Obtel. All rights reserved.
"""Summarise a harvested external-aero case: coefficients, breakdown, WP-01 checks, plots.

    PYTHONIOENCODING=utf-8 python cfd/tools/report_case.py cfd/cases/<case>

Reads results/<alpha tag>/postProcessing (forceCoeffs, residuals, yPlus), the
mesh logs (log.snappyHexMesh, log.checkMesh) and constant/geometry/reference.
Writes RESULTS.md and results/<tag>/convergence.pdf/.png.

WP-01 rules checked for every angle (00_START_HERE_RnD.md Sec. 2a): solver and
version, turbulence model, y+ (mean and max), cell count, residual drop
(at least 3 orders), a flat force history over the last 200 iterations, and the
reference area, length, density, viscosity and speed.
Values are mean over the last 200 iterations; "spread" is max - min there.
Verdict "pass" needs mean y+ <= 1.5 on every patch, every residual down 3 orders,
C_L spread <= 0.5 % (0.002 near zero lift) and C_D spread <= 1 %.
"""
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "design-system" / "matplotlib"))
LAST = 200
PATCH_FO = {"coeffs": "aircraft", "coeffsWing": "wing", "coeffsFuselage": "fuselage",
            "coeffsVtail": "vtail", "coeffsNacelle": "nacelle"}


def foam_value(path, key):
    m = re.search(rf"^\s*{key}\s+([^;]+);", path.read_text(), re.M)
    return m.group(1).strip() if m else None


def table(path):
    """OpenFOAM function-object .dat: (column names, float rows); text columns dropped."""
    names, rows = None, []
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            parts = line[1:].split()
            if parts and parts[0] == "Time":
                names = parts
            continue
        if line.strip():
            rows.append(line.split())
    return names, rows


def dats(run, fo, name):
    """A function object's .dat files, one per start time (a resumed run adds one); fo may be a glob."""
    return sorted(run.glob(f"postProcessing/{fo}/*/{name}"), key=lambda p: float(p.parent.name))


def dat(run, fo, name):
    files = dats(run, fo, name)
    return files[-1] if files else None


def history(run, fo, name):
    """(column names, rows) over every restart. Rows an earlier file holds from the next start
    time on were recomputed after that restart (which restates the start time), so they are dropped."""
    files = dats(run, fo, name)
    names, rows = None, []
    for i, p in enumerate(files):
        n, r = table(p)
        names = names or n
        if i + 1 < len(files):
            r = [x for x in r if float(x[0]) < float(files[i + 1].parent.name)]
        rows += r
    return names, rows


def coeffs(run, fo):
    names, rows = history(run, fo, "forceCoeffs.dat")
    if not rows:
        return None
    a = np.array([[float(x) for x in r] for r in rows])
    return {n: a[:, i] for i, n in enumerate(names)}


def flat(c, window=LAST):
    """WP-01 flat force history: C_L within 0.5 % (0.002 near zero lift) and C_D within 1 % over the window.
    Returns (ok, mean, spread, tolerance) for Cl, Cd (and Cm in mean, spread)."""
    m = {k: c[k][-window:].mean() for k in ("Cl", "Cd", "Cm")}
    sp = {k: np.ptp(c[k][-window:]) for k in ("Cl", "Cd", "Cm")}
    tol = {"Cl": max(0.005 * abs(m["Cl"]), 0.002), "Cd": 0.01 * m["Cd"]}
    return all(sp[k] <= tol[k] for k in tol), m, sp, tol


def residuals(run):
    names, rows = history(run, "residuals*", "residuals.dat")   # directory is residuals(p,U,...)
    if not rows:
        return None
    out = {}
    for i, n in enumerate(names):
        col = [r[i] for r in rows]
        try:
            out[n] = np.array([float(x) if x != "N/A" else np.nan for x in col])
        except ValueError:
            pass
    return out


def yplus(run):
    p = dat(run, "yPlus", "yPlus.dat")
    if not p:
        return {}
    _, rows = table(p)
    last = rows[-1][0]
    return {r[1]: tuple(float(x) for x in r[2:5]) for r in rows if r[0] == last}


def mesh_info(case):
    info = {}
    cm = case / "log.checkMesh"
    if cm.exists():
        t = cm.read_text()
        m = re.search(r"cells:\s+(\d+)", t)
        info["cells"] = int(m.group(1)) if m else None
        m = re.search(r"non-orthogonality (?:Max:|= )\s*([\d.]+) average: ([\d.]+)", t)   # OF14, older
        info["nonortho"] = (float(m.group(1)), float(m.group(2))) if m else None
        m = re.search(r"Max skewness = ([\d.]+)", t)
        info["skew"] = float(m.group(1)) if m else None
        info["ok"] = "Mesh OK." in t
        info["failed"] = re.findall(r"\*\*\*(.+)", t)
    # one snappyHexMesh pass, or castellate/snap then layers (log.snappyHexMesh.layers)
    logs = [p for p in (case / "log.snappyHexMesh", case / "log.snappyHexMesh.layers") if p.exists()]
    if logs:
        t = logs[-1].read_text()
        blk = t[t.rfind("Doing final balancing"):] if "Doing final balancing" in t else t
        info["layers"] = re.findall(r"^(\w+)\s+(\d+)\s+([\d.]+)\s+([\d.e+-]+)\s+([\d.]+)\s*$", blk, re.M)
        m = [re.findall(r"Finished meshing in = ([\d.]+) s", p.read_text()) for p in logs]
        info["snappy_s"] = sum(float(x[-1]) for x in m if x) or None
    return info


def plot(run, c, res, tag):
    import dbfplot as dp
    dp.use()
    fig, axs = dp.figure("page", 4.2, nrows=2, ncols=2)
    it = c["Time"]
    for ax, key, lab in ((axs[0, 0], "Cl", "$C_L$"), (axs[0, 1], "Cd", "$C_D$"), (axs[1, 0], "Cm", "$C_m$")):
        ax.plot(it, c[key], color=dp.INK, lw=0.8)
        tail = c[key][-LAST:]
        pad = max(5 * (tail.max() - tail.min()), 0.02 * abs(tail.mean()), 1e-4)
        ax.set_ylim(tail.mean() - pad, tail.mean() + pad)
        ax.axvspan(it[-min(LAST, len(it))], it[-1], color=dp.MIST, lw=0)
        ax.set_xlabel("iteration")
        ax.set_ylabel(lab)
    ax = axs[1, 1]
    greys = [dp.INK, dp.GRAPHITE, dp.STEEL, dp.FOG, dp.INK, dp.STEEL, dp.GRAPHITE]
    styles = ["-", "-", "-", "-", "--", "--", ":"]
    k = 0
    for n, v in res.items():
        if n == "Time" or np.all(np.isnan(v)):
            continue
        ax.semilogy(res["Time"], v, color=greys[k % 7], ls=styles[k % 7], lw=0.7, label=n.replace("_initial", ""))
        k += 1
    ax.set_xlabel("iteration")
    ax.set_ylabel("initial residual")
    ax.legend(ncol=2, fontsize=6, frameon=False)
    fig.tight_layout()
    dp.save(fig, run / "convergence.pdf")
    fig.savefig(run / "convergence.png", dpi=200)


def main(case):
    ref = case / "constant" / "geometry" / "reference"
    par = case / "system" / "caseParameters"
    S, mac = float(foam_value(ref, "Sref")), float(foam_value(ref, "refLength"))
    span, cofr = float(foam_value(ref, "span")), foam_value(ref, "refCofR")
    U, nu, rho = (float(foam_value(par, k)) for k in ("UMag", "nuAir", "rhoDesign"))
    q = 0.5 * rho * U * U
    mesh = mesh_info(case)
    runs = sorted((case / "results").glob("alpha*"), key=lambda p: float(p.name[5:]))
    rows, checks, brk = [], [], []
    for run in runs:
        a = float(foam_value(run / "alphaState", "alphaDeg"))
        c = coeffs(run, "coeffs")
        if c is None:
            continue
        res = residuals(run) or {}
        yp = yplus(run)
        ok_flat, m, spread, _ = flat(c)
        ends = {}   # field: (initial residual at the start, worst over the last LAST)
        for n, v in res.items():
            if n.endswith("_initial") or (n != "Time" and "_" not in n):
                v = v[~np.isnan(v)]
                if len(v) > 10:
                    ends[n.replace("_initial", "")] = (v[:5].max(), v[-LAST:].max())
        start = next(run.glob("log.start.*"), None)
        warm = start is not None and start.read_text().startswith("warm")
        rows.append((a, m, spread, len(c["Time"])))
        for fo, nm in PATCH_FO.items():
            cp = coeffs(run, fo)
            if cp is not None and nm != "aircraft":
                w = cp["Time"] > cp["Time"][-1] - LAST   # the breakdown is written every 10th iteration
                brk.append((a, nm, cp["Cl"][w].mean(), cp["Cd"][w].mean(), cp["Cm"][w].mean()))
        checks.append((a, yp, ends, warm, spread, m, ok_flat))
        if res:
            plot(run, c, res, run.name)

    L = [f"# {case.name}: results", "",
         "Generated by `cfd/tools/report_case.py` from the harvested run. Coefficients are full-aircraft values (half-model force on S/2), "
         f"mean of the last {LAST} iterations.", "",
         "## Conditions and references", "",
         "| Item | Value |", "|---|---|",
         "| Solver | OpenFOAM 14, `foamRun -solver incompressibleFluid`, steady SIMPLEC |",
         "| Turbulence | `kOmegaSSTLM` (Langtry–Menter γ-Reθ transition SST) |",
         f"| Speed, density, viscosity | {U:g} m/s, {rho:g} kg/m³, ν {nu:.4g} m²/s |",
         f"| Re on the MAC | {U * mac / nu:,.0f} |",
         f"| Reference area, MAC, span | {S:.5g} m², {mac:.5g} m, {span:.4g} m |",
         f"| Moment reference | {cofr} m (CFD frame) |",
         f"| Mesh | {mesh.get('cells', 0):,} cells (half model); checkMesh {'OK' if mesh.get('ok') else 'FAILED: ' + '; '.join(mesh.get('failed', []))}; "
         f"max non-orthogonality {mesh['nonortho'][0] if mesh.get('nonortho') else '?'}°, max skewness {mesh.get('skew', '?')} |", "",
         "## Coefficients", "",
         "| α body (°) | α wing (°) | C_L | C_D | C_D (counts) | L/D | C_m | L (N) | D (N) | iterations |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for a, m, sp, n in rows:
        L.append(f"| {a:+.1f} | {a + 2.48:+.2f} | {m['Cl']:.4f} | {m['Cd']:.5f} | {1e4 * m['Cd']:.1f} | {m['Cl'] / m['Cd']:.1f} | "
                 f"{m['Cm']:+.4f} | {m['Cl'] * q * S:.3f} | {m['Cd'] * q * S:.4f} | {n} |")
    L += ["", "α wing = α body + 2.48° (wing incidence to the fuselage datum, from the CAD). L and D at the design density, whole aircraft.", ""]
    if brk:
        L += ["## Breakdown by patch", "", "| α body (°) | patch | C_L | C_D | share of C_D | C_m |", "|---|---|---|---|---|---|"]
        tot = {a: m["Cd"] for a, m, _, _ in rows}
        for a, nm, cl, cd, cm in brk:
            L.append(f"| {a:+.1f} | {nm} | {cl:.4f} | {cd:.5f} | {100 * cd / tot[a]:.0f} % | {cm:+.4f} |")
        L.append("")
    L += ["## WP-01 checks", "", "| α body (°) | y+ mean / max (worst patch) | residual drop, orders (min field) | "
          f"spread over last {LAST}: C_L, C_D | verdict |", "|---|---|---|---|---|"]
    # A warm start begins near the previous angle's converged residuals, so its own drop says nothing;
    # it is measured from the initial residuals of the cold start(s) the warm-start chain began with.
    cold = {}
    for _, _, ends, warm, *_ in checks:
        for n, (s, _f) in ends.items():
            if not warm:
                cold[n] = max(cold.get(n, 0), s)
    for a, yp, ends, warm, sp, m, ok_flat in checks:
        ymean = max((v[2] for v in yp.values()), default=float("nan"))
        ymax, ypatch = max(((v[1], k) for k, v in yp.items()), default=(float("nan"), "?"))
        vs_cold = warm and all(n in cold for n in ends)
        drops = {n: np.log10((cold[n] if vs_cold else s) / f) for n, (s, f) in ends.items()}
        dmin, dfield = min(((v, k) for k, v in drops.items()), default=(float("nan"), "?"))
        ok = (ymean <= 1.5) and (dmin >= 3) and ok_flat
        L.append(f"| {a:+.1f} | {ymean:.2f} / {ymax:.1f} ({ypatch}) | {dmin:.1f} ({dfield}{', from cold start' if vs_cold else ''}) | "
                 f"{sp['Cl']:.2g}, {sp['Cd']:.2g} ({100 * sp['Cd'] / m['Cd']:.2f} %) | {'pass' if ok else 'CHECK'} |")
    if any(w for _, _, _, w, *_ in checks):
        L += ["", "Warm-started angles begin from the previous angle's solution; their residual drop is measured "
              "from the initial residuals of the cold start that began the chain."]
    if mesh.get("layers"):
        L += ["", "## Prism layers (snappyHexMesh)", "", "| patch | faces | layers (mean) | thickness (m) | % of target |", "|---|---|---|---|---|"]
        L += [f"| {p} | {f} | {n} | {t} | {pc} |" for p, f, n, t, pc in mesh["layers"]]
    (case / "RESULTS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
