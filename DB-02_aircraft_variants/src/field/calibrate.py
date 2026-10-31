"""Calibration, back-test and evidence tables for the S2 field model (functions only; run via run_s2.py).

Everything here reads the AIAA 2022-26 data through model.py and writes nothing by itself.

Sections
  1. moments        rank statistics linking report, completion and value (observed with bootstrap SE, simulated)
  2. fit            weighted moment matching of the latent loadings (chi-square, Nelder-Mead)
  3. backtest       simulate each past year (in-sample and leave-one-year-out) against the real results
  4. shape / report tables      fraction-of-max shapes and report-score marginals, observed vs simulated
  5. attempts       per-attempt success by mission from the 2023-26 attempt counts
  6. stall          Bayesian logistic of M2 success on stall speed (15 top-3 aircraft)
  7. scale prior    physics bound for M2, M3 and GM evidence, GM declaration sensitivity
"""
from __future__ import annotations

import csv
import math

import numpy as np
from scipy.stats import rankdata

from . import model as fm

MOMENT_KEYS = ("rs_report_total", "auc_tech", "auc_flew", "auc_m2", "auc_m3", "auc_gm",
               "rs_report_b2", "rs_report_b3", "rs_b2_b3", "p_gm_given_m3")


# ---------------------------------------------------------------------------- 1. moments
def _rankdata(x):
    return rankdata(np.asarray(x, float), method="average")


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 4:
        return np.nan
    ra, rb = _rankdata(a), _rankdata(b)
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def auc(score, label):
    """P(score of a positive > score of a negative), ties half (Mann-Whitney)."""
    score, label = np.asarray(score, float), np.asarray(label, bool)
    pos, neg = int(label.sum()), int((~label).sum())
    if pos < 2 or neg < 2:
        return np.nan
    r = _rankdata(score)
    return float((r[label].sum() - pos * (pos + 1) / 2) / (pos * neg))


def _moments(rep, tot, flew, tech, d1, d2, d3, dg, b2, b3):
    both = d2 & d3
    return {
        "rs_report_total": spearman(rep, tot),
        "auc_tech": auc(rep, tech) if tech is not None else np.nan,
        "auc_flew": auc(rep[tech], flew[tech]) if tech is not None else np.nan,
        "auc_m2": auc(rep[d1], d2[d1]),
        "auc_m3": auc(rep[d2], d3[d2]),
        "auc_gm": auc(rep[tech] if tech is not None else rep, (dg[tech] if tech is not None else dg)),
        "rs_report_b2": spearman(rep[d2], b2[d2]),
        "rs_report_b3": spearman(rep[d3], b3[d3]),
        "rs_b2_b3": spearman(b2[both], b3[both]),
        "p_gm_given_m3": float(dg[d3].mean()) if d3.sum() else np.nan,
    }


def _year_arrays(y):
    """Real attendees of year y as arrays (report, total, tech, flew, d1, d2, d3, dg, b2, b3)."""
    A = fm.attendees(y)
    rep = np.array([r["report"] or 0.0 for r in A])
    tot = np.array([r["total"] or 0.0 for r in A])
    d1 = np.array([(r["m1"] or 0) > 0 for r in A])
    d2 = np.array([(r["m2"] or 0) > 0 for r in A]) & d1
    d3 = np.array([(r["m3"] or 0) > 0 for r in A]) & d2
    dg = np.array([(r["gm"] or 0) > 0 for r in A])
    b2 = np.array([(r["m2"] or 0) - 1.0 for r in A])
    b3 = np.array([(r["m3"] or 0) - 2.0 for r in A])
    if y in fm.YEARS_P:
        tech = np.array([r["p"] >= 2 for r in A])
        flew = np.array([r["p"] >= 3 for r in A])
    else:
        tech = flew = None
    return rep, tot, tech, flew, d1, d2, d3, dg, b2, b3


def observed_moments(boot=300, seed=5):
    """Observed moments per year with bootstrap standard errors (teams resampled within year)."""
    rng = np.random.default_rng(seed)
    out = {}
    for y in fm.YEARS:
        arr = _year_arrays(y)
        base = _moments(*arr)
        n = len(arr[0])
        acc = {k: [] for k in MOMENT_KEYS}
        for _ in range(boot):
            ix = rng.integers(0, n, n)
            sub = tuple(a[ix] if a is not None else None for a in arr)
            m = _moments(*sub)
            for k in MOMENT_KEYS:
                acc[k].append(m[k])
        se = {k: float(np.nanstd(acc[k])) for k in MOMENT_KEYS}
        out[y] = {"value": base, "se": se, "n": n}
    return out


def pooled_observed(obs, years=fm.YEARS):
    """Inverse-variance pooled observed moment over `years` (NaN years skipped) and its standard error."""
    res = {}
    for k in MOMENT_KEYS:
        v = np.array([obs[y]["value"][k] for y in years])
        s = np.maximum(np.array([obs[y]["se"][k] for y in years]), 0.03)
        ok = np.isfinite(v) & np.isfinite(s)
        w = 1.0 / s[ok] ** 2
        res[k] = (float((v[ok] * w).sum() / w.sum()), float(1.0 / math.sqrt(w.sum())), ok)
    return res


def simulated_moments(year, n=100, seed=0, params=None, loo=False):
    """Mean of each moment over n simulated fly-offs of a past year (+ the Field and totals)."""
    F = fm.simulate(n, seed, year=year, params=params, loo=loo)
    tot, _, _ = fm.mission_scores(F)
    acc = {k: [] for k in MOMENT_KEYS}
    for i in range(n):
        a = F.attend[i]
        tech = F.tech[i][a] if year in fm.YEARS_P else None
        flew = F.flew[i][a] if year in fm.YEARS_P else None
        m = _moments(F.report[i][a], tot[i][a], flew, tech, F.done["M1"][i][a], F.done["M2"][i][a],
                     F.done["M3"][i][a], F.done["GM"][i][a], F.m2_wt[i][a], F.m3_lxs[i][a])
        for k in MOMENT_KEYS:
            acc[k].append(m[k])
    return {k: float(np.nanmean(acc[k])) for k in MOMENT_KEYS}, F, tot


def chi2(params, obs, years=fm.YEARS, n=60, seed=11, detail=False):
    """Chi-square of the pooled moments (simulated mean vs inverse-variance pooled observed)."""
    po = pooled_observed(obs, years)
    sims = {y: simulated_moments(y, n=n, seed=seed + y, params=params)[0] for y in years}
    tot, rows = 0.0, {}
    for k in MOMENT_KEYS:
        o, se, _ = po[k]
        vals = [sims[y][k] for y in years if obs[y]["value"][k] == obs[y]["value"][k]]
        s = float(np.nanmean(vals)) if vals else np.nan
        z = (s - o) / max(se, 0.02)
        tot += z * z
        rows[k] = {"observed": o, "se": se, "simulated": s, "z": z}
    return (tot, rows) if detail else tot


FIT_NAMES = ("lam_report", "lam_tech", "lam_flight", "lam_gm", "lam_value", "rho_m2m3")


def _to_params(x):
    return {k: float(math.tanh(v) * 0.95) for k, v in zip(FIT_NAMES, x)}


def fit(obs=None, n=60, seed=11, maxfev=160, x0=None):
    """Weighted moment matching of the six latent parameters. Returns dict with params, chi2, rows, curvature SE."""
    from scipy.optimize import minimize
    obs = obs or observed_moments()
    start = np.arctanh(np.array([fm.PARAMS[k] for k in FIT_NAMES]) / 0.95) if x0 is None else np.asarray(x0)
    f = lambda x: chi2(_to_params(x), obs, n=n, seed=seed)
    res = minimize(f, start, method="Nelder-Mead", options={"maxfev": maxfev, "xatol": 0.02, "fatol": 0.05})
    best = _to_params(res.x)
    c0, rows = chi2(best, obs, n=3 * n, seed=seed + 1000, detail=True)
    # conditional curvature SE: sigma = sqrt(2 / f'')
    se = {}
    for i, k in enumerate(FIT_NAMES):
        h = 0.08
        xp, xm = res.x.copy(), res.x.copy()
        xp[i] += h
        xm[i] -= h
        fp = chi2(_to_params(xp), obs, n=2 * n, seed=seed + 1000)
        fm_ = chi2(_to_params(xm), obs, n=2 * n, seed=seed + 1000)
        curv = max((fp + fm_ - 2 * c0) / (h * h), 1e-6)
        dtheta = 0.95 * (1 - math.tanh(res.x[i]) ** 2)
        se[k] = float(math.sqrt(2.0 / curv) * dtheta)
    return {"params": best, "chi2": c0, "rows": rows, "se_conditional": se, "evals": int(res.nfev),
            "chi2_start": chi2({k: fm.PARAMS[k] for k in FIT_NAMES}, obs, n=3 * n, seed=seed + 1000)}


# ---------------------------------------------------------------------------- 3. back-test
def _top_stats(tot, att):
    """Per draw: best, second-best mission total over attending teams."""
    x = np.where(att, tot, -np.inf)
    s = -np.sort(-x, axis=1)
    return s[:, 0], s[:, 1]


def pit(sample, obs_value):
    """Randomisation-free PIT: P(X < obs) + 0.5 P(X == obs)."""
    s = np.asarray(sample, float)
    return float((s < obs_value - 1e-9).mean() + 0.5 * (np.abs(s - obs_value) <= 1e-9).mean())


def backtest(n=2000, seed=100, params=None):
    """Simulate each past year with that year's formulas, in-sample (own year's counts) and LOO.

    Returns {mode: {year: stats}} with the simulated distribution summaries of the quantities that
    matter for P(1st): winner's mission total, best and second-best mission total, number of teams
    completing all four missions, and per-mission completers; and the observed values with PIT.
    """
    E = fm.empirical()
    out = {}
    for mode, loo in (("in_sample", False), ("loo", True)):
        out[mode] = {}
        for y in fm.YEARS:
            F = fm.simulate(n, seed + y, year=y, params=params, loo=loo)
            tot, _, _ = fm.mission_scores(F)
            att = F.attend
            comp = np.where(att, F.report * tot + (F.participation if y != 2022 else 0), -np.inf)
            w = np.argmax(comp, axis=1)
            win_total = tot[np.arange(n), w]
            best, second = _top_stats(tot, att)
            call = (F.done["M1"] & F.done["M2"] & F.done["M3"] & F.done["GM"]).sum(axis=1)
            rows = {
                "winner_total": win_total, "best_total": best, "second_total": second, "completed_all": call,
                "m1": F.done["M1"].sum(axis=1), "m2": F.done["M2"].sum(axis=1), "m3": F.done["M3"].sum(axis=1),
                "gm": F.done["GM"].sum(axis=1),
            }
            obsv = {"winner_total": E["winner_total"][y], "best_total": E["max_total"][y], "second_total": E["second_total"][y],
                    "completed_all": E["completed_all"][y], **{k: E["completed"][y][k] for k in ("m1", "m2", "m3", "gm")}}
            out[mode][y] = {k: {"obs": float(obsv[k]), "mean": float(v.mean()), "sd": float(v.std()),
                                "p10": float(np.percentile(v, 10)), "p50": float(np.percentile(v, 50)),
                                "p90": float(np.percentile(v, 90)), "pit": pit(v, obsv[k]), "sample": v}
                            for k, v in rows.items()}
    return out


def pit_summary(bt, keys=("winner_total", "best_total", "second_total", "completed_all", "m2", "m3", "gm")):
    """Per mode: share of observed values inside the simulated P10-P90 (nominal 0.80), mean |PIT - 0.5|, KS of PITs vs U(0,1)."""
    from scipy.stats import kstest
    res = {}
    for mode, d in bt.items():
        res[mode] = {}
        for k in keys:
            p = np.array([d[y][k]["pit"] for y in fm.YEARS])
            inside = np.mean([d[y][k]["p10"] <= d[y][k]["obs"] <= d[y][k]["p90"] for y in fm.YEARS])
            res[mode][k] = {"inside_p10_p90": float(inside), "pits": p.tolist(), "ks_p": float(kstest(p, "uniform").pvalue),
                            "bias_z": float(np.mean([(d[y][k]["mean"] - d[y][k]["obs"]) / max(d[y][k]["sd"], 1e-9) for y in fm.YEARS]))}
    return res


# ---------------------------------------------------------------------------- 4. shapes and reports
def shape_table(n=800, seed=300, params=None):
    """Fraction-of-max: observed (field_bonus.csv) vs simulated (second, p75, median, p25) per year and mission."""
    rows = list(csv.DictReader((fm.DATA / "field_bonus.csv").open(encoding="utf-8")))
    obs = {(int(r["year"]), r["mission"]): r for r in rows}
    out = {}
    for y in fm.YEARS:
        F = fm.simulate(n, seed + y, year=y, params=params)
        for m, arr, dn in (("M2", F.m2_wt, F.done["M2"]), ("M3", F.m3_lxs, F.done["M3"])):
            stats = []
            for i in range(n):
                v = np.sort(arr[i][dn[i]])[::-1]
                if len(v) < 4:
                    continue
                v = v / v[0]
                stats.append([v[1], np.percentile(v, 75), np.median(v), np.percentile(v, 25)])
            s = np.mean(stats, axis=0)
            o = obs[(y, m)]
            out[(y, m)] = {"observed": [float(o["second"]), float(o["p75"]), float(o["median"]), float(o["p25"])],
                           "simulated": [float(x) for x in s], "completers_obs": int(o["completers"])}
    return out


def report_table(n=400, seed=400, params=None):
    """Report-score marginals of attendees: observed vs simulated mean, sd, P10, P50, P90, top-10 median."""
    out = {}
    for y in fm.YEARS:
        rep = np.array([r["report"] or 0.0 for r in fm.attendees(y)])
        F = fm.simulate(n, seed + y, year=y, params=params)
        sims = []
        for i in range(n):
            r = F.report[i][F.attend[i]]
            top10 = np.sort(r)[::-1][:10]
            sims.append([r.mean(), r.std(), *np.percentile(r, [10, 50, 90]), np.median(top10)])
        s = np.mean(sims, axis=0)
        top10 = np.sort(rep)[::-1][:10]
        o = [rep.mean(), rep.std(), *np.percentile(rep, [10, 50, 90]), np.median(top10)]
        out[y] = {"observed": [float(x) for x in o], "simulated": [float(x) for x in s]}
    return out


# ---------------------------------------------------------------------------- 5. attempts
def attempt_targets(years=fm.YEARS_P):
    """Observed per flying team: M1 completion, M2|M1, M3|M2, attempts used, scored attempts (2023-26)."""
    E = fm.empirical()
    rows = []
    for y in years:
        o = fm.OFFICIAL[y]
        flew = len([r for r in fm.attendees(y) if r["p"] >= 3])
        c = E["completed"][y]
        rows.append([c["m1"] / flew, c["m2"] / c["m1"], c["m3"] / c["m2"], o["attempts"] / flew, o["scored"] / flew])
    return np.array(rows)


def _sim_attempts(p, budget_pmf, q_end, n=40000, seed=1):
    rng = np.random.default_rng(seed)
    b, pr = budget_pmf
    c = fm.sample_completion(p[1], p[2], rng, n, waive_m1=False, p_m1=p[0], attempts=rng.choice(b, size=n, p=pr), q_end=q_end)
    d1, d2, d3 = c["done_m1"], c["done_m2"], c["done_m3"]
    # completion of the stage requires the preceding one; n_flew = n
    return np.array([d1.mean(), d2.sum() / max(d1.sum(), 1), d3.sum() / max(d2.sum(), 1),
                     c["n_attempts_used"].mean(), c["n_scored"].mean()])


def _binom_pmf(lo, k, pb):
    b = np.arange(lo, lo + k + 1)
    from scipy.stats import binom
    return b, binom.pmf(np.arange(k + 1), k, pb)


BUDGET_FAMILIES = {   # attempt-slot distributions tried (min slots + Binomial)
    "1+Bin(5,pb)": (1, 5), "2+Bin(4,pb)": (2, 4), "1+Bin(4,pb)": (1, 4),
}


def fit_attempts(q_ends=(0.0, 0.15, 0.30)):
    """Per-attempt success p1, p2, p3 and the slot distribution that reproduce the 2023-26 attempt counts.

    Fit by least squares on the mean of the 2023-26 per-flying-team targets (5 numbers) with 4 parameters
    (p1, p2, p3, pb); scaled by the year-to-year sd of each target. Returns the fit for each budget
    family and q_end, so the spread is the structural uncertainty.
    """
    from scipy.optimize import minimize
    T = attempt_targets()
    tmean, tsd = T.mean(axis=0), np.maximum(T.std(axis=0, ddof=1), 0.02)
    res = {}
    sig = lambda x: 1 / (1 + np.exp(-x))
    for fam, (lo, k) in BUDGET_FAMILIES.items():
        for q in q_ends:
            def loss(x):
                p = sig(x[:3])
                pb = sig(x[3])
                s = _sim_attempts(p, _binom_pmf(lo, k, pb), q, n=20000, seed=3)
                return float((((s - tmean) / tsd) ** 2).sum())
            r = minimize(loss, [0.6, 0.4, 0.0, 0.0], method="Nelder-Mead", options={"maxiter": 220, "xatol": 0.02, "fatol": 0.02})
            p = sig(r.x[:3])
            pb = float(sig(r.x[3]))
            s = _sim_attempts(p, _binom_pmf(lo, k, pb), q, n=60000, seed=9)
            res[(fam, q)] = {"p": [float(v) for v in p], "pb": pb, "loss": float(r.fun), "targets": tmean.tolist(), "fitted": s.tolist(),
                             "mean_slots": float(lo + k * pb)}
    return {"targets": tmean.tolist(), "target_sd": tsd.tolist(), "fits": res}


# ---------------------------------------------------------------------------- 6. stall speed
STALL_DATA = [   # year, team, wing loading at max gross [N/m2] (dbf_airframes.csv), M2 scored, M3 scored
    (2022, "FH Joanneum", 111.232, 1, 1), (2022, "MIT", 112.474, 0, 0), (2022, "WashU", 64.885, 1, 1),
    (2023, "ERAU", 231.408, 1, 1), (2023, "Washington", 141.916, 1, 1), (2023, "Virginia Tech", 150.776, 1, 1),
    (2024, "Ljubljana", 103.278, 0, 0), (2024, "USC", 123.846, 1, 0), (2024, "Virginia Tech", 172.555, 1, 1),
    (2025, "ERAU", 256.909, 0, 0), (2025, "UCLA", 169.367, 1, 1), (2025, "UNSW", 248.236, 0, 0),
    (2026, "Georgia Tech", 53.413, 1, 1), (2026, "Ljubljana", 97.826, 1, 1), (2026, "USC", 98.983, 1, 0),
]


def stall_estimates(cl_eff=1.8, rho=1.15):
    """Stall speed [m/s] of the 15 aircraft at max gross: sqrt(2 WL / (rho CLmax)); CLmax_eff 1.8 (+-0.33, 5 reported
    stall speeds imply 1.4-2.2), rho 1.15 (Wichita/Tucson April, estimate)."""
    return np.array([math.sqrt(2 * wl / (rho * cl_eff)) for _, _, wl, _, _ in STALL_DATA])


def fit_stall(outcome="m2", attempts=3, prior_median=0.25, prior_sigma=0.7, cl_eff=1.8, v_ref=12.0):
    """Posterior of the logit slope b_v [per m/s above v_ref] from the outcome of 15 aircraft.

    P(team scores | per-attempt p, A attempts) = 1 - (1 - p)^A, logit p = b0 - b_v max(0, Vs - v_ref); prior on log b_v
    lognormal(prior_median, prior_sigma), b0 ~ N(0.6, 1). Grid posterior. Returns quantiles of b_v and the prior's.
    """
    vs = stall_estimates(cl_eff)
    y = np.array([r[3] if outcome == "m2" else r[4] for r in STALL_DATA], float)
    bs = np.exp(np.linspace(np.log(0.01), np.log(3.0), 240))
    b0s = np.linspace(-2.5, 4.0, 240)
    over = np.maximum(0.0, vs - v_ref)
    lp = np.zeros((len(bs), len(b0s)))
    for i, b in enumerate(bs):
        p = 1 / (1 + np.exp(-(b0s[None, :] - b * over[:, None])))
        pt = np.clip(1 - (1 - p) ** attempts, 1e-9, 1 - 1e-9)
        lp[i] = np.where(y[:, None] > 0, np.log(pt), np.log(1 - pt)).sum(axis=0) - 0.5 * ((b0s - 0.6) / 1.0) ** 2
    lpr = -0.5 * ((np.log(bs) - np.log(prior_median)) / prior_sigma) ** 2
    L = lp + lpr[:, None]
    w = np.exp(L - L.max())
    wb = w.sum(axis=1)
    wb /= wb.sum()
    pr = np.exp(lpr)
    pr /= pr.sum()
    q = lambda dens: [float(bs[np.searchsorted(np.cumsum(dens), x)]) for x in (0.1, 0.5, 0.9)]
    return {"posterior_p10_p50_p90": q(wb), "prior_p10_p50_p90": q(pr), "vs": vs.tolist(), "attempts": attempts,
            "outcome": outcome, "cl_eff": cl_eff}


# ---------------------------------------------------------------------------- 7. scale prior
G = 9.80665


def m2_energy_bound(eta, e, cd0_f, lap_fac, af, clmax, vs_max, rho=1.064, span=1.82, wh_usable=80.0, bank_max=75):
    """Largest W_payload/t [kg/s] over 5 laps for one parameter set (brute force over S, W, V, bank).

    Energy: parabolic polar (CD0 = 0.0086 + cd0_f / S, Oswald e), course of rules 3.3.3 (609.6 m straights + 4 pi r of
    turns per lap), propulsive energy / eta <= usable Wh, stall W <= 0.5 rho Vs^2 CLmax S / g, turn CL <= 0.95 CLmax,
    airframe 5.96 S^0.94 af + 1.52 kg (pack, D&R, misc), time 5 laps x lap_fac + 8 s. No take-off energy, no wind.
    """
    best = (0.0,)
    for S in np.arange(0.6, 1.5, 0.1):
        ar = span * span / S
        mair = 5.96 * S ** 0.94 * af + 1.52
        cd0 = 0.0086 + cd0_f / S
        wmax = min(0.5 * rho * vs_max ** 2 * clmax * S / G, 24.9)
        for W in np.arange(mair + 1, wmax + 0.01, 0.5):
            for V in np.arange(18, 40, 1.0):
                q = 0.5 * rho * V * V
                for bank in np.arange(50, bank_max + 1, 5):
                    n = 1 / math.cos(math.radians(bank))
                    cl_t = n * W * G / (q * S)
                    if cl_t > 0.95 * clmax:
                        continue
                    r = V * V / (G * math.tan(math.radians(bank)))
                    turns = 4 * math.pi * r
                    L = 609.6 + turns
                    cl_s = W * G / (q * S)
                    ds = q * S * (cd0 + cl_s ** 2 / (math.pi * ar * e))
                    dt = q * S * (cd0 + cl_t ** 2 / (math.pi * ar * e))
                    E = 5 * (ds * 609.6 + dt * turns) / eta / 3600
                    if E > wh_usable:
                        continue
                    t = 5 * L / V * lap_fac + 8.0
                    rate = (W - mair) / t
                    if rate > best[0]:
                        best = (rate, S, W, V, bank, t, E)
    return best


M2_BOUND_CASES = {   # (eta, e, cd0_f, lap_fac, af, CLmax, Vs_max): central = DB-01 / accepted S3; optimistic; all-optimistic
    "central (DB-01 inputs)": (0.58, 0.90, 0.013, 1.15, 1.0, 1.6, 14),
    "optimistic": (0.65, 0.95, 0.013, 1.05, 0.9, 1.9, 14),
    "all-optimistic": (0.70, 1.00, 0.008, 1.00, 0.8, 2.2, 14),
}


def m3_multiplier_draws(n=20000, seed=3):
    """Monte Carlo of the M3 rival maximum / 27 kg*laps: best of K specialist teams, laps x towed sensor mass.

    Laps ~ {6: .15, 7: .35, 8: .35, 9: .15} (lap time 33-39 s in a 300 s window, ledger O-08/O-09, 2021 towed paces 34-54 s);
    towed sensor mass lognormal(median 3.0 kg, sigma 0.35) (competitor.toml 2.6-3.7 kg); K ~ 3 specialists. Estimate.
    """
    rng = np.random.default_rng(seed)
    K = 3
    laps = rng.choice([6, 7, 8, 9], size=(n, K), p=[0.15, 0.35, 0.35, 0.15])
    m = 3.0 * np.exp(0.35 * rng.standard_normal((n, K)))
    return (laps * m).max(axis=1) / 27.0


def gm_sensitivity(q_means=(0.02, 0.05, 0.10, 0.20), n=3000, seed=21):
    """P(some rival declares >= 6 kg and survives) and the implied GM multiplier, against the heavy-share prior."""
    out = {}
    for q in q_means:
        r = fm.gm_heavy_probability(n, seed, 6.0, params={"gm_q_mean": q})
        out[q] = {"p_ge6": r["p"], "ci95": r["ci95"], "mult_p50": r["multiplier_q"][50], "mult_p10": r["multiplier_q"][10],
                  "mult_p90": r["multiplier_q"][90], "p_max_ge_9_1": r["p_max_ge_9_1"]}
    return out


def gm_sensitivity_slope(slopes=(0.0, 0.05, 0.10, 0.15), n=3000, seed=21):
    out = {}
    for s in slopes:
        r = fm.gm_heavy_probability(n, seed, 6.0, params={"gm_rel_slope": s})
        out[s] = {"p_ge6": r["p"], "mult_p50": r["multiplier_q"][50]}
    return out
