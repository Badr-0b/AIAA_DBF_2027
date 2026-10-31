"""S2 field model and reliability for DB-02 (2026-27 DBF, "UAV with Sensor Suite"). VERSION v1.

Public API (pure functions, SI units, no I/O on import; data files are read lazily, read-only):

    simulate(n, seed, year=2027, scale=None, params=None, loo=False) -> Field
    p_first(our, rivals, report_score, participation=3) -> dict
    p_first_curve(our, rivals, report_scores) -> list[dict]
    p_attempt(margins, complexity, mission="M2") -> float
    p_attempt_breakdown(margins, complexity, mission="M2") -> dict
    sample_completion(p_m2, p_m3, rng, n, waive_m1=True, p_m1=None, p_gm=0.9, attempts=None) -> dict
    p_complete(probs, attempts) -> float          (same recursion as analysis/data/attempts.py)
    day_conditions(n, seed, hour=None) -> dict
    lap_time_wind_factor(V, wind, r_turn, along=1.0) -> float|array
    crosswind(wind, angle_deg) -> float|array

New optional functions in v1 (the v0 signatures are unchanged):

    p_attempt_interval(margins, complexity, mission, n, seed) -> dict   coefficient-uncertainty band
    density_table(hours) -> dict                                       KTUS density P10/P50/P90 by hour
    gm_heavy_probability(n, seed, threshold_kg, params) -> dict         P(some rival declares >= x and survives)

Field model (a Gaussian copula with empirical marginals; method and validation in
W/memos/02_field_reliability.md):
  * one latent strength z per rival team drives its report score, its mission completion
    (threshold "liability" per stage) and its mission values (rank of its fraction of the max);
  * marginals are resampled from the AIAA 2022-26 results (analysis/data/dbf_results.csv,
    513 rows): number attending, conditional completion rates, report scores, and each
    mission's fractions of the field maximum among completers;
  * the absolute 2027 scale of the M2 and M3 rival maxima = competitor.toml aggressive
    anchor x a lognormal multiplier (prior in PARAMS, derivation in the memo);
  * the 2027 Ground Mission is modelled mechanically: each rival declares a sensor mass, some
    declare heavy, heavy units survive the drops less often, and the rival maximum is the largest
    surviving mass x height (no multiplier needed; `scale` rescales it when given);
  * our values enter each mission maximum in p_first (the max includes ours, rules 3.3.3).

All coefficients are grade `estimate` unless stated; see PARAMS, ATTEMPTS, COEF, HAZARD and the memo.
"""
from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W = HERE.parents[1]
REPO = W.parent
DATA = REPO / "analysis" / "data"
RAW = DATA / "raw"
THP = W / "out" / "field" / "raw" / "iem_TUS_thp_apr.csv"     # KTUS T, dew point, altimeter (IEM)
T_SLOTS = 100                       # team slots per draw (attending rivals <= 96 in 2022-26)
YEARS = (2022, 2023, 2024, 2025, 2026)
YEARS_P = (2023, 2024, 2025, 2026)  # years with a participation column (attend / tech / flew)
MISSIONS = ("m2", "m3", "gm")

# AIAA competition summaries (verified, aiaa-dbf-<y>-results.txt, first paragraph)
OFFICIAL = {   # attended, passed tech, official flight attempts, scored attempts, teams with >=1 score, all four
    2022: dict(attended=64, tech=58, attempts=152, scored=87, any_score=40, all_four=15),
    2023: dict(attended=82, tech=74, attempts=203, scored=124, any_score=54, all_four=22),
    2024: dict(attended=93, tech=85, attempts=236, scored=156, any_score=65, all_four=31),
    2025: dict(attended=96, tech=92, attempts=267, scored=164, any_score=78, all_four=24),
    2026: dict(attended=89, tech=83, attempts=197, scored=143, any_score=73, all_four=17),
}

# ---------------------------------------------------------------------------- parameters
# v1 (30 Oct 2026). Latent loadings are CALIBRATED (calibrate.fit, weighted moment matching on the
# 2022-26 results, see memo S2-R*). The 2027 scale priors and the GM declaration model are ESTIMATES
# derived in the memo (physics bound + 2025 analog + a mechanical GM model); each carries a range.
PARAMS = {
    # latent loadings: corr(liability or rank, team strength z)
    "lam_report": 0.60,     # report score rank
    "lam_tech": 0.45,       # passing tech and flying at all
    "lam_flight": 0.60,     # M1, M2|M1, M3|M2 completion
    "lam_gm": 0.40,         # GM completion
    "lam_value": 0.45,      # rank of a completer's value (fraction of the max)
    "rho_m2m3": 0.30, "rho_m2gm": 0.60, "rho_m3gm": 0.30,   # value-rank residual correlations (past GM)
    # 2027 scale prior on the rival maxima (lognormal multiplier on the competitor.toml aggressive anchor)
    "m2_median": 0.70, "m2_sigma": 0.20,
    "m3_median": 0.85, "m3_sigma": 0.30,
    "scale_corr": 0.50,     # shared field-strength correlation between the M2 and M3 multipliers
    "report_jitter": 1.0,   # points, sd, on resampled report scores
    # 2027 Ground Mission declaration model (mass x height, drops on concrete)
    "gm_q_mean": 0.10, "gm_q_kappa": 12.0,        # share of tech-passers declaring heavy ~ Beta (mean, concentration)
    "gm_heavy_median": 6.5, "gm_heavy_sigma": 0.25, "gm_heavy_cap": 12.0,    # kg
    "gm_light_median": 2.8, "gm_light_sigma": 0.45, "gm_light_cap": 4.5,     # kg
    "gm_lam_heavy": 0.40,   # stronger teams more likely to go heavy
    "gm_h_full": 0.85,      # share declaring the full 1.524 m; the rest 0.8-1.524 m
    "gm_rel_m0": 4.5, "gm_rel_slope": 0.10, "gm_rel_floor": 0.20,   # drop-survival factor 1 - slope (m - m0)
    "gm_novelty": (0.60, 1.00),                  # destructive drop test is new: multiplier on the past GM rate
}


# ---------------------------------------------------------------------------- data (lazy)
def _f(x):
    return float(x) if x not in (None, "") else None


@lru_cache(maxsize=1)
def _results():
    rows = list(csv.DictReader((DATA / "dbf_results.csv").open(encoding="utf-8")))
    for r in rows:
        r["year"] = int(r["year"])
        for k in ("p", "gm", "m1", "m2", "m3", "total", "proposal", "design", "report", "score"):
            r[k] = _f(r.get(k))
    return rows


def attendees(y):
    """Rows of the teams that attended in year y.

    2023-26: participation score >= 1 (verified column). 2022 has no participation column: the 64
    attendees (AIAA summary) are the 51 teams with a mission score plus the 13 best-reported of the
    other 46 (estimate; 2023-26 attendees' mean report rank is 43-50 of 99-112 vs 72-88 for absentees).
    """
    R = [r for r in _results() if r["year"] == y]
    if y in YEARS_P:
        return [r for r in R if (r["p"] or 0) >= 1]
    scored = [r for r in R if (r["total"] or 0) > 0]
    rest = sorted((r for r in R if not (r["total"] or 0) > 0), key=lambda r: -(r["report"] or 0))
    return scored + rest[:max(0, OFFICIAL[y]["attended"] - len(scored))]


@lru_cache(maxsize=1)
def empirical():
    """Per-year field statistics read from dbf_results.csv (verified rows). Cached dict."""
    rows = _results()
    out = {"attend_n": {}, "rates": {}, "reports": {}, "shapes": {}, "winner_total": {},
           "max_total": {}, "second_total": {}, "completed_all": {}, "completed": {}, "totals": {}}
    for y in YEARS:
        R = [r for r in rows if r["year"] == y]
        A = attendees(y)
        if y in YEARS_P:
            tech = [r for r in A if r["p"] >= 2]
            flew = [r for r in A if r["p"] >= 3]
        else:
            tech, flew = None, None
        m1 = [r for r in A if (r["m1"] or 0) > 0]
        m2 = [r for r in m1 if (r["m2"] or 0) > 0]
        m3 = [r for r in m2 if (r["m3"] or 0) > 0]
        gm = [r for r in A if (r["gm"] or 0) > 0]
        out["attend_n"][y] = len(A)
        if tech is not None:
            out["rates"][y] = {"tech": len(tech) / len(A), "flew": len(flew) / len(tech),
                               "m1": len(m1) / len(flew), "m2": len(m2) / len(m1),
                               "m3": len(m3) / len(m2), "gm": len(gm) / len(tech)}
        out["reports"][y] = np.array(sorted((r["report"] or 0.0 for r in A), reverse=True))
        out["shapes"][(y, "m2")] = np.array(sorted((r["m2"] - 1.0 for r in m2), reverse=True))
        out["shapes"][(y, "m3")] = np.array(sorted((r["m3"] - 2.0 for r in m3), reverse=True))
        out["shapes"][(y, "gm")] = np.array(sorted((r["gm"] for r in gm), reverse=True))
        win = [r for r in R if str(r["rank"]) == "1"][0]
        tots = sorted((r["total"] for r in R), reverse=True)
        out["winner_total"][y] = win["total"]
        out["max_total"][y], out["second_total"][y] = tots[0], tots[1]
        out["totals"][y] = np.array(tots)
        out["completed_all"][y] = sum(1 for r in A if all((r[m] or 0) > 0 for m in ("gm", "m1", "m2", "m3")))
        out["completed"][y] = {"m1": len(m1), "m2": len(m2), "m3": len(m3), "gm": len(gm)}
    # 2022: tech from the AIAA summary (58 of 64); flew pooled from 2023-26 (estimate); flight stages from counts.
    flew_pool = float(np.mean([out["rates"][y]["flew"] for y in YEARS_P]))
    c, o = out["completed"][2022], OFFICIAL[2022]
    nflew = o["tech"] * flew_pool
    out["rates"][2022] = {"tech": o["tech"] / o["attended"], "flew": flew_pool,
                          "m1": min(1.0, c["m1"] / nflew), "m2": c["m2"] / c["m1"], "m3": c["m3"] / c["m2"],
                          "gm": min(1.0, c["gm"] / o["tech"])}
    return out


@lru_cache(maxsize=1)
def anchors():
    """Aggressive anchors {m2: kg/s, m3: kg*laps, gm: kg*m} from analysis/common.field_maxima."""
    sys.dont_write_bytecode = True
    ana = str(REPO / "analysis")
    if ana not in sys.path:
        sys.path.insert(0, ana)
    import common  # read-only: loads analysis/inputs/*.toml
    return dict(common.field_maxima("aggressive"))


_UGRID = np.linspace(0.0, 1.0, 201)


@lru_cache(maxsize=None)
def _qgrid(key):
    """Quantile function (201 points) of the non-leader fractions of one (year, mission) shape."""
    v = empirical()["shapes"][key]
    rest = v[1:] if len(v) > 1 else v
    return np.quantile(rest, _UGRID)


# ---------------------------------------------------------------------------- helpers
def _rank_desc(key):
    """Rank (0 = largest) of each entry along axis 1; -inf entries rank last."""
    n, t = key.shape
    order = np.argsort(-key, axis=1, kind="stable")
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.broadcast_to(np.arange(t), (n, t)).copy(), axis=1)
    return rank


def _latent(rng, z, lam):
    return lam * z + math.sqrt(max(0.0, 1.0 - lam * lam)) * rng.standard_normal(z.shape)


def _stage(rng, prev, latent, rate):
    """Pass the top-k of `prev` by `latent`, k ~ Binomial(count(prev), rate) per draw."""
    k = rng.binomial(prev.sum(axis=1), np.clip(rate, 0.0, 1.0))
    rank = _rank_desc(np.where(prev, latent, -np.inf))
    return prev & (rank < k[:, None])


def _interp_rows(Q, u):
    """Row-wise linear interpolation of quantile grids Q (n, 201) at u (n, T) in [0, 1]."""
    x = u * (len(_UGRID) - 1)
    i0 = np.clip(np.floor(x).astype(int), 0, len(_UGRID) - 2)
    w = x - i0
    return (1 - w) * np.take_along_axis(Q, i0, axis=1) + w * np.take_along_axis(Q, i0 + 1, axis=1)


@dataclass
class Field:
    """One simulated fly-off per row. Arrays are (n, T) unless noted; masked by `attend`."""
    n: int
    T: int
    year: int
    attend: np.ndarray
    tech: np.ndarray
    flew: np.ndarray
    participation: np.ndarray
    report: np.ndarray
    done: dict
    m2_wt: np.ndarray
    m3_lxs: np.ndarray
    gm_wh: np.ndarray
    rival_max: dict
    scale: np.ndarray
    ref_year: np.ndarray
    shape_year: dict
    gm_mass: np.ndarray = None        # declared sensor mass of each rival (2027 only), kg
    gm_heavy_share: np.ndarray = None  # (n,) share of tech-passers declaring heavy (2027 only)

    def values(self, m):
        return {"m2": self.m2_wt, "m3": self.m3_lxs, "gm": self.gm_wh}[m]


def _gm_declare(rng, n, T, z, tech, dg, P):
    """2027 Ground Mission: declared mass x height of every rival, and who survives the drops.

    Returns (dg_after_drops, gm_wh, mass, q).  Estimates throughout (no drop-test history exists):
    heavy declarers ~ Beta(q_mean, kappa) share of the tech-passers, picked by a strength latent;
    declared mass lognormal (heavy / light), capped by what the airframe can lift into the M2 unit;
    survival factor 1 - slope (m - m0) (floor), applied on top of the past GM completion rate.
    """
    q_mean, kap = P["gm_q_mean"], P["gm_q_kappa"]
    q = rng.beta(q_mean * kap, (1 - q_mean) * kap, size=n)
    nt = tech.sum(axis=1)
    k = rng.binomial(nt, q)
    lat = _latent(rng, z, P["gm_lam_heavy"])
    heavy = tech & (_rank_desc(np.where(tech, lat, -np.inf)) < k[:, None])
    zn = rng.standard_normal((n, T))
    m_h = np.clip(P["gm_heavy_median"] * np.exp(P["gm_heavy_sigma"] * zn), P["gm_light_cap"], P["gm_heavy_cap"])
    m_l = np.clip(P["gm_light_median"] * np.exp(P["gm_light_sigma"] * rng.standard_normal((n, T))), 0.5, P["gm_light_cap"])
    mass = np.where(heavy, m_h, m_l)
    h = np.where(rng.random((n, T)) < P["gm_h_full"], 1.524,
                 np.floor(rng.uniform(0.8, 1.524, (n, T)) / 0.0254) * 0.0254)
    rel = np.clip(1.0 - P["gm_rel_slope"] * (mass - P["gm_rel_m0"]), P["gm_rel_floor"], 1.0)
    survive = rng.random((n, T)) < rel
    dg2 = dg & survive
    return dg2, np.where(dg2, mass * h, 0.0), mass, q


# ---------------------------------------------------------------------------- simulate
def simulate(n, seed, year=2027, scale=None, params=None, loo=False):
    """Simulate `n` fly-offs of rival teams (vectorised).

    year=2027: each draw resamples a reference year 2023-26 for the number attending, the
    completion rates and the report scores, and an independent shape year 2022-26 per mission.
    M2 and M3 values are absolute (kg/s, kg*laps) with the rival maximum = anchor x lognormal
    multiplier; the GM comes from the declaration model (kg*m), rescaled to scale x anchor if `scale`
    is given.
    year=2022..2026: back-test of that year, values in units of that year's field max (scale 1).
    loo=True (back-test only): the number attending, completion rates, report scores and mission
    shapes are all drawn from the OTHER years (leave-one-year-out); loo=False reuses the year itself.
    scale: None (draw the prior), a float (all missions) or a 3-sequence (M2, M3, GM).
    """
    P = {**PARAMS, **(params or {})}
    E = empirical()
    rng = np.random.default_rng(seed)
    T = T_SLOTS
    past = year != 2027
    if past and not loo:
        ref = np.full(n, year)
    elif past:
        ref = rng.choice(np.array([y for y in YEARS_P if y != year]), size=n)
    else:
        ref = rng.choice(np.array(YEARS_P), size=n)
    N = np.array([E["attend_n"][y] for y in ref])
    attend = np.arange(T)[None, :] < N[:, None]
    z = rng.standard_normal((n, T))

    def rate(k):
        return np.array([E["rates"][y][k] for y in ref])

    tech = _stage(rng, attend, _latent(rng, z, P["lam_tech"]), rate("tech"))
    flew = _stage(rng, tech, _latent(rng, z, P["lam_tech"]), rate("flew"))
    d1 = _stage(rng, flew, _latent(rng, z, P["lam_flight"]), rate("m1"))
    d2 = _stage(rng, d1, _latent(rng, z, P["lam_flight"]), rate("m2"))
    d3 = _stage(rng, d2, _latent(rng, z, P["lam_flight"]), rate("m3"))
    if past:
        rg = rate("gm")
    else:   # 2027: GM rate from the 2022-26 timed ground missions x a novelty factor (drops are destructive)
        rg = np.array([E["rates"][y]["gm"] for y in rng.choice(np.array(YEARS), size=n)])
        lo, hi = P["gm_novelty"]
        rg = rg * rng.uniform(lo, hi, size=n)
    dg = _stage(rng, tech, _latent(rng, z, P["lam_gm"]), rg)
    participation = attend.astype(int) + tech + flew

    # report scores: that reference year's attending reports, assigned by report-latent rank
    rl = _latent(rng, z, P["lam_report"])
    rank_r = _rank_desc(np.where(attend, rl, -np.inf))
    report = np.zeros((n, T))
    for y in np.unique(ref):
        rows = np.where(ref == y)[0]
        vals = E["reports"][y]
        rr = np.minimum(rank_r[rows], len(vals) - 1)
        report[rows] = vals[rr]
    report = np.clip(report + P["report_jitter"] * rng.standard_normal((n, T)), 0.0, 100.0)
    report = np.where(attend, report, 0.0)

    # value-rank latents with cross-mission residual correlation
    C = np.array([[1.0, P["rho_m2m3"], P["rho_m2gm"]],
                  [P["rho_m2m3"], 1.0, P["rho_m3gm"]],
                  [P["rho_m2gm"], P["rho_m3gm"], 1.0]])
    L = np.linalg.cholesky(C)
    eta = rng.standard_normal((n, T, 3)) @ L.T
    lv = P["lam_value"]
    V = lv * z[..., None] + math.sqrt(1 - lv * lv) * eta

    # scale multipliers
    gm_mass = gm_q = None
    if past:
        k = np.ones((n, 3))
        anc = {"m2": 1.0, "m3": 1.0, "gm": 1.0}
    else:
        anc = anchors()
        if scale is None:
            rc = P["scale_corr"]
            common_ = rng.standard_normal((n, 1))
            own = rng.standard_normal((n, 3))
            zz = math.sqrt(rc) * common_ + math.sqrt(1 - rc) * own
            k = np.ones((n, 3))
            k[:, 0] = P["m2_median"] * np.exp(P["m2_sigma"] * zz[:, 0])
            k[:, 1] = P["m3_median"] * np.exp(P["m3_sigma"] * zz[:, 1])
        else:
            k = np.broadcast_to(np.asarray(scale, float).reshape(-1), (3,)) * np.ones((n, 3))

    vals_out, rival_max, shape_year = {}, {}, {}
    for j, m in enumerate(MISSIONS):
        dm = {"m2": d2, "m3": d3, "gm": dg}[m]
        if m == "gm" and not past:
            dg2, gmv, gm_mass, gm_q = _gm_declare(rng, n, T, z, tech, dg, P)
            done_gm = dg2
            mx = gmv.max(axis=1)
            if scale is not None:
                f = np.where(mx > 0, k[:, 2] * anc["gm"] / np.where(mx > 0, mx, 1.0), 0.0)
                gmv = gmv * f[:, None]
                mx = mx * f
            k[:, 2] = mx / anc["gm"]
            vals_out[m], rival_max[m] = gmv, mx
            shape_year[m] = np.zeros(n, int)
            continue
        nc = dm.sum(axis=1)
        if past:
            keys = [(yy, m) for yy in YEARS if (not loo or yy != year)]
        else:
            keys = [(yy, m) for yy in YEARS]
        if past and not loo:
            keys = [(year, m)]
        pick = rng.integers(0, len(keys), size=n) if len(keys) > 1 else np.zeros(n, int)
        Q = np.stack([_qgrid(kk) for kk in keys])[pick]                 # (n, 201)
        shape_year[m] = np.array([keys[i][0] for i in pick])
        f = _interp_rows(Q, rng.random((n, T)))
        valid = np.arange(T)[None, :] < (nc - 1)[:, None]
        f = -np.sort(-np.where(valid, f, -np.inf), axis=1)               # descending
        F = np.concatenate([np.ones((n, 1)), f[:, :T - 1]], axis=1)
        F = np.where(np.isfinite(F), F, 0.0)
        rank_v = _rank_desc(np.where(dm, V[..., j], -np.inf))
        frac = np.where(dm, np.take_along_axis(F, np.minimum(rank_v, T - 1), axis=1), 0.0)
        top = anc[m] * k[:, j]
        vals_out[m] = frac * top[:, None]
        rival_max[m] = np.where(nc > 0, top, 0.0)
    if not past:
        dg = dg2
    done = {"M1": d1, "M2": d2, "M3": d3, "GM": dg}
    return Field(n=n, T=T, year=year, attend=attend, tech=tech, flew=flew, participation=participation,
                 report=report, done=done, m2_wt=vals_out["m2"], m3_lxs=vals_out["m3"], gm_wh=vals_out["gm"],
                 rival_max=rival_max, scale=k, ref_year=ref, shape_year=shape_year,
                 gm_mass=gm_mass, gm_heavy_share=gm_q)


def gm_heavy_probability(n=4000, seed=7, threshold_kg=6.0, params=None):
    """P(at least one rival declares >= threshold_kg AND completes the drops), and the rival GM maximum.

    Uses the same declaration model as simulate(2027). Returns dict with the probability, its
    Wilson interval, the quantiles of the rival maximum in kg*m and the implied multiplier on the
    12.19 kg*m anchor.
    """
    F = simulate(n, seed, 2027, params=params)
    ok = (F.done["GM"] & (F.gm_mass >= threshold_kg)).any(axis=1)
    mx = F.rival_max["gm"]
    a = anchors()["gm"]
    k = int(ok.sum())
    return {"threshold_kg": threshold_kg, "p": k / n, "ci95": _wilson(k, n),
            "max_kg_m_q": {q: float(np.percentile(mx, q)) for q in (5, 10, 25, 50, 75, 90, 95)},
            "multiplier_q": {q: float(np.percentile(mx / a, q)) for q in (5, 10, 25, 50, 75, 90, 95)},
            "p_max_ge_9_1": float((mx >= 6.0 * 1.524).mean()), "n": n}


# ---------------------------------------------------------------------------- scoring
def _gm_base(year):
    return 0.5 if year == 2027 else 0.0


def _bcast(x, n, dtype=float):
    a = np.asarray(x, dtype=dtype).reshape(-1)
    if a.size == 1:
        return np.full(n, a[0], dtype=dtype)
    return np.resize(a, n)


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mission_scores(rivals, our=None):
    """Total Mission Score of every rival (n, T) and ours (n,), each maximum including ours."""
    n = rivals.n
    vals = {"m2": rivals.m2_wt, "m3": rivals.m3_lxs, "gm": rivals.gm_wh}
    dn = {"m2": rivals.done["M2"], "m3": rivals.done["M3"], "gm": rivals.done["GM"]}
    base = {"m2": 1.0, "m3": 2.0, "gm": _gm_base(rivals.year)}
    if our is not None:
        o = {k: _bcast(our.get(k, 0.0), n) for k in ("m2_wt", "m3_lxs", "gm_wh")}
        od = {k: _bcast(our.get(k, False), n, bool) for k in ("done_m1", "done_m2", "done_m3", "done_gm")}
        ov = {"m2": o["m2_wt"], "m3": o["m3_lxs"], "gm": o["gm_wh"]}
        odn = {"m2": od["done_m2"], "m3": od["done_m3"], "gm": od["done_gm"]}
    riv_tot = rivals.done["M1"].astype(float)
    our_parts = {"M1": od["done_m1"].astype(float)} if our is not None else None
    for m in MISSIONS:
        mx = rivals.rival_max[m]
        if our is not None:
            mx = np.maximum(mx, np.where(odn[m], ov[m], 0.0))
        safe = np.where(mx > 0, mx, 1.0)
        riv_tot = riv_tot + np.where(dn[m], base[m] + vals[m] / safe[:, None], 0.0)
        if our is not None:
            our_parts[m.upper()] = np.where(odn[m], base[m] + ov[m] / safe, 0.0)
    our_tot = sum(our_parts.values()) if our is not None else None
    return riv_tot, our_tot, our_parts


def p_first(our, rivals, report_score, participation=3):
    """P(highest mission total), P(1st overall) and rank against a simulated field.

    our: dict of (n,) arrays or scalars: m2_wt [kg/s], m3_lxs [kg*laps], gm_wh [kg*m],
         done_m1, done_m2, done_m3, done_gm [bool]; optional flew [bool] (default True).
    report_score: our Total Report Score (0-100), scalar or (n,).
    """
    n = rivals.n
    riv_tot, our_tot, parts = mission_scores(rivals, our)
    att = rivals.attend
    best_riv = np.where(att, riv_tot, -np.inf).max(axis=1)
    top = np.where(our_tot > best_riv + 1e-12, 1.0, np.where(np.abs(our_tot - best_riv) <= 1e-12, 0.5, 0.0))
    rep = _bcast(report_score, n)
    flew = _bcast(our.get("flew", True), n, bool)
    our_part = np.where(flew, participation, 2)
    our_comp = rep * our_tot + our_part
    riv_comp = np.where(att, rivals.report * riv_tot + rivals.participation, -np.inf)
    beats = (riv_comp > our_comp[:, None] + 1e-9) | ((np.abs(riv_comp - our_comp[:, None]) <= 1e-9)
                                                   & (rivals.report > rep[:, None]))
    rank = 1 + beats.sum(axis=1)
    k_top, k_first = float(top.sum()), int((rank == 1).sum())
    sd = float(rank.std(ddof=1)) if n > 1 else 0.0
    return {
        "n": n,
        "p_mission_top": k_top / n, "p_mission_top_ci95": _wilson(k_top, n),
        "p_first": k_first / n, "p_first_ci95": _wilson(k_first, n),
        "rank_mean": float(rank.mean()),
        "rank_mean_ci95": (float(rank.mean() - 1.96 * sd / math.sqrt(n)), float(rank.mean() + 1.96 * sd / math.sqrt(n))),
        "rank_p10": float(np.percentile(rank, 10)), "rank_p50": float(np.percentile(rank, 50)),
        "rank_p90": float(np.percentile(rank, 90)),
        "rank": rank, "top": top, "our_total": our_tot, "our_parts": parts, "winner_rival_total": best_riv,
    }


def p_first_curve(our, rivals, report_scores=tuple(range(70, 97, 2)), participation=3):
    """p_first over a list of our report scores (same draws). List of dicts with key report_score."""
    out = []
    for r in report_scores:
        d = p_first(our, rivals, r, participation)
        out.append({"report_score": r, **{k: d[k] for k in ("p_first", "p_first_ci95", "p_mission_top",
                                                          "rank_mean", "rank_p50")}})
    return out


# ---------------------------------------------------------------------------- reliability
# Field-typical margins. v_stall 12.0 = median of the 15 top-3 aircraft with a fly-off result (memo S2-R14);
# the others are estimates (no data), only used when the caller omits the key.
TYPICAL = {
    "v_stall": 12.0, "v_ref": 12.0, "tw_takeoff": 0.45, "cl_turn_ratio": 0.80, "n_turn": 2.9,
    "n_gust_p90": 1.0, "staging_margin_s": 120.0, "energy_reserve": 0.15, "crosswind_ratio": 0.25,
    "pilot_hours_type": 5.0,
}
# Field-typical per-attempt success of a team that is attempting that mission: fitted to the AIAA
# 2023-26 attempt counts and completion fractions (calibrate.fit_attempts), estimate with range.
P_TYPICAL = {"M1": 0.70, "M2": 0.60, "M3": 0.50}
COEF = {   # logit coefficients; every one is an estimate, ranges in COEF_RANGE
    "b_v": 0.45,        # per m/s of stall speed above v_ref (Bayesian logistic on 15 top-3 aircraft, calibrate.fit_stall)
    "b_v_lo": 0.10,     # per m/s below v_ref (gentle, capped at 3 m/s of benefit)
    "b_roll": 1.0,      # per e-fold of take-off roll beyond L0 (estimate, no data)
    "L0": 60.0,         # m, roll length the field is comfortable with (estimate; runway length not in the repo)
    "b_cl": 1.2, "cl0": 0.90,
    "sig_stage_s": 40.0, "sig_energy": 0.10, "b_x": 0.4, "x0": 0.30, "b_h": 0.25,
}
COEF_RANGE = {"b_v": (0.20, 0.80), "b_v_lo": (0.0, 0.25), "b_roll": (0.5, 2.0), "b_cl": (0.6, 2.0),
              "b_x": (0.2, 0.8), "b_h": (0.10, 0.40)}
HAZARD = {   # extra per-attempt failure probability, multiplicative on p (1 - h); estimates with ranges
    "retract": 0.03, "twin": 0.04, "multi_surface": 0.03, "slotted_flap": 0.01, "fowler": 0.03,
    "vtail": 0.01, "pusher": 0.01, "tailless": 0.04, "dr_drum": 0.0, "dr_complex": 0.012,
}
HAZARD_RANGE = {"retract": (0.01, 0.08), "twin": (0.015, 0.10), "multi_surface": (0.01, 0.08),
                "slotted_flap": (0.003, 0.03), "fowler": (0.01, 0.08), "vtail": (0.0, 0.03),
                "pusher": (0.0, 0.03), "tailless": (0.01, 0.10), "dr_drum": (0.0, 0.0), "dr_complex": (0.004, 0.04)}
G = 9.80665


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def roll_length(v_stall, tw):
    """Take-off ground roll [m]: lift-off at 1.1 x 1.2 x V_stall, mean thrust 0.8 x static, rolling friction 0.04."""
    a = G * max(0.8 * tw - 0.04, 0.02)
    return (1.32 * v_stall) ** 2 / (2.0 * a)


def _terms(m, c=None):
    c = c or COEF
    r_eff = m["cl_turn_ratio"] * (m["n_turn"] + m["n_gust_p90"]) / m["n_turn"]
    dv = m["v_stall"] - m["v_ref"]
    stall = -c["b_v"] * dv if dv > 0 else c["b_v_lo"] * min(-dv, 3.0)
    roll = roll_length(m["v_stall"], m["tw_takeoff"])
    return {
        "stall": stall,
        "takeoff_roll": -c["b_roll"] * min(max(0.0, math.log(roll / c["L0"])), 4.0),
        "turn_cl_gust": -c["b_cl"] * max(0.0, (r_eff - c["cl0"]) / 0.1),
        "crosswind": -c["b_x"] * max(0.0, (m["crosswind_ratio"] - c["x0"]) / 0.1),
        "pilot": c["b_h"] * math.log(max(m["pilot_hours_type"], 0.5) / TYPICAL["pilot_hours_type"]),
    }


def _ok(m):
    return {"staging": _norm_cdf(m["staging_margin_s"] / COEF["sig_stage_s"]),
            "energy": _norm_cdf(m["energy_reserve"] / COEF["sig_energy"])}


def _features(complexity):
    parts = [p.strip().lower() for p in str(complexity).replace(",", "+").split("+") if p.strip()]
    feats = [p for p in parts if p != "simple"]
    unknown = [p for p in feats if p not in HAZARD]
    if unknown:
        raise ValueError(f"unknown complexity feature(s) {unknown}; known: {sorted(HAZARD)}")
    return feats


def _breakdown(margins, complexity, mission, c=None, hz=None):
    mission = mission.upper()
    hz = hz or HAZARD
    m = {**TYPICAL, **(margins or {})}
    t, t0 = _terms(m, c), _terms(TYPICAL, c)
    ok, ok0 = _ok(m), _ok(TYPICAL)
    p0 = P_TYPICAL[mission] / (ok0["staging"] * ok0["energy"])
    b0 = math.log(p0 / (1 - p0)) - sum(t0.values())
    logit = b0 + sum(t.values())
    p_fly = 1.0 / (1.0 + math.exp(-logit))
    feats = _features(complexity)
    haz = {f: hz[f] for f in feats if not (f.startswith("dr_") and mission != "M3")}
    surv = float(np.prod([1 - h for h in haz.values()])) if haz else 1.0
    p = p_fly * ok["staging"] * ok["energy"] * surv
    return {"mission": mission, "b0": b0, "terms": t, "ok": ok, "hazards": haz, "p_flight": p_fly, "p": p,
            "roll_m": roll_length(m["v_stall"], m["tw_takeoff"])}


def p_attempt_breakdown(margins, complexity="simple", mission="M2"):
    """Every term of p_attempt: logit terms, multiplicative OK-probabilities, feature hazards."""
    return _breakdown(margins, complexity, mission)


def p_attempt(margins, complexity="simple", mission="M2"):
    """P(one attempt at `mission` is scored) from design margins and complexity (see API doc)."""
    return _breakdown(margins, complexity, mission)["p"]


def p_attempt_interval(margins, complexity="simple", mission="M2", n=2000, seed=0):
    """Coefficient-uncertainty band of p_attempt: coefficients and hazards drawn log-uniformly from
    COEF_RANGE / HAZARD_RANGE (uniform where a range touches zero); P_TYPICAL drawn +-0.07."""
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    mission = mission.upper()
    saved = P_TYPICAL[mission]
    try:
        for i in range(n):
            c = dict(COEF)
            for k, (lo, hi) in COEF_RANGE.items():
                c[k] = lo + (hi - lo) * rng.random() if lo <= 0 else math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * rng.random())
            hz = {k: lo + (hi - lo) * rng.random() for k, (lo, hi) in HAZARD_RANGE.items()}
            P_TYPICAL[mission] = float(np.clip(saved + 0.07 * (2 * rng.random() - 1), 0.05, 0.95))
            out[i] = _breakdown(margins, complexity, mission, c, hz)["p"]
    finally:
        P_TYPICAL[mission] = saved
    return {"p": p_attempt(margins, complexity, mission), "p10": float(np.percentile(out, 10)),
            "p50": float(np.percentile(out, 50)), "p90": float(np.percentile(out, 90)), "n": n}


def p_complete(probs, attempts):
    """P(all missions in `probs` completed, in order, within `attempts` tries) (attempts.py logic)."""
    @lru_cache(maxsize=None)
    def go(i, left):
        if i == len(probs):
            return 1.0
        if left == 0:
            return 0.0
        p = probs[i]
        return p * go(i + 1, left - 1) + (1 - p) * go(i, left - 1)
    return go(0, attempts)


# Flight-attempt budget of a team (attempt slots incl. the two extra attempts) and P(airframe out
# for the contest | failed attempt). Budget = 1 + Binomial(5, 0.5) fitted to the 2023-26 counts
# (calibrate.fit_attempts): mean 3.5 slots, of which a team uses 2.9 on average (it stops when done).
ATTEMPTS = {"budget": (1, 2, 3, 4, 5, 6), "probs": (0.03125, 0.15625, 0.3125, 0.3125, 0.15625, 0.03125), "q_end": 0.15}


def sample_completion(p_m2, p_m3, rng, n, waive_m1=True, p_m1=None, p_gm=0.9, attempts=None, q_end=None):
    """Draw mission completion for our team over the flight-attempt budget.

    Missions in order (M1 unless waived, M2, M3), a failed attempt is retried while attempts
    remain; after a failed attempt the airframe is out for the contest with probability q_end;
    after all three, one extra M2 and one extra M3 attempt (rules 3.3.3) if the budget allows.
    p_* may be scalars or (n,) arrays. Returns bool arrays done_m1..done_gm and counts of scored
    M2/M3 attempts (n_m2_scores, n_m3_scores).
    """
    p_m1 = P_TYPICAL["M1"] if p_m1 is None else p_m1
    q_end = ATTEMPTS["q_end"] if q_end is None else q_end
    p1, p2, p3 = (_bcast(p, n) for p in (p_m1, p_m2, p_m3))
    if attempts is None:
        A = rng.choice(np.array(ATTEMPTS["budget"]), size=n, p=np.array(ATTEMPTS["probs"]))
    else:
        A = _bcast(attempts, n, int)
    stage = np.where(waive_m1, 1, 0)          # 0: M1, 1: M2, 2: M3, 3: extra M2, 4: extra M3, 5: done
    alive = np.ones(n, bool)
    d1 = np.zeros(n, bool); d2 = np.zeros(n, bool); d3 = np.zeros(n, bool)
    s2 = np.zeros(n, int); s3 = np.zeros(n, int)
    used = np.zeros(n, int); scored = np.zeros(n, int)
    for a in range(int(A.max())):
        act = alive & (a < A) & (stage < 5)
        pr = np.select([stage == 0, (stage == 1) | (stage == 3), (stage == 2) | (stage == 4)], [p1, p2, p3], 0.0)
        ok = act & (rng.random(n) < pr)
        fail = act & ~ok
        used += act
        scored += ok
        d1 |= ok & (stage == 0)
        d2 |= ok & ((stage == 1) | (stage == 3))
        d1 |= d2
        d3 |= ok & ((stage == 2) | (stage == 4))
        s2 += ok & ((stage == 1) | (stage == 3))
        s3 += ok & ((stage == 2) | (stage == 4))
        adv = ok | (fail & (stage >= 3))      # extra attempts are one-shot
        stage = np.where(act & adv, stage + 1, stage)
        alive &= ~(fail & (rng.random(n) < q_end))
    dg = rng.random(n) < _bcast(p_gm, n)
    return {"done_m1": d1, "done_m2": d2, "done_m3": d3, "done_gm": dg, "n_m2_scores": s2, "n_m3_scores": s3,
            "attempts": A, "n_attempts_used": used, "n_scored": scored}


# ---------------------------------------------------------------------------- conditions
KT = 1852.0 / 3600.0
TIMPA_ELEV_M = 667.0


@lru_cache(maxsize=1)
def _wind_obs():
    """Hourly sustained wind, gust and direction, 15-18 Apr, 07-18 h, RYN + AVQ + TUS (IEM)."""
    rows = []
    for st in ("RYN", "AVQ", "TUS"):
        p = RAW / f"iem_{st}_apr.csv"
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            v = r["valid"]
            day, hour = int(v[8:10]), int(v[11:13])
            if not (15 <= day <= 18 and 7 <= hour <= 18) or r["sknt"] in ("M", ""):
                continue
            g = float(r["gust"]) * KT if r["gust"] not in ("M", "") else float("nan")
            d = float(r["drct"]) if r["drct"] not in ("M", "") else float("nan")
            rows.append((hour, float(r["sknt"]) * KT, g, d))
    return np.array(rows) if rows else np.zeros((0, 4))


def moist_air_density(tmpf, dwpf, alti_inhg, elev_m=TIMPA_ELEV_M):
    """Moist-air density [kg/m3] at elev_m from KTUS T [F], dew point [F], altimeter [inHg].

    Method of REPO/proposal/data/numbers.tex (\\nRho): station pressure P = A ((288 - 0.0065 h)/288)^5.2561
    (NWS altimeter reduction), vapour pressure from the dew point (Magnus), rho = Pd/(Rd T) + Pv/(Rv T).
    """
    T = (np.asarray(tmpf, float) - 32.0) / 1.8
    Td = (np.asarray(dwpf, float) - 32.0) / 1.8
    P = np.asarray(alti_inhg, float) * 3386.389 * ((288.0 - 0.0065 * elev_m) / 288.0) ** 5.2561
    pv = 611.2 * np.exp(17.62 * Td / (243.12 + Td))
    Tk = T + 273.15
    return (P - pv) / (287.058 * Tk) + pv / (461.495 * Tk)


@lru_cache(maxsize=1)
def _thp_obs():
    """KTUS hourly rows 15-18 Apr 1996-2025: columns year, day, hour, temp_c, rho. Empty if the file is absent."""
    if not THP.exists():
        return np.zeros((0, 5))
    rows = []
    for r in csv.DictReader(THP.open(encoding="utf-8")):
        if "M" in (r["tmpf"], r["dwpf"], r["alti"]):
            continue
        v = r["valid"]
        day, hour = int(v[8:10]), int(v[11:13])
        if not (15 <= day <= 18):
            continue
        rho = float(moist_air_density(float(r["tmpf"]), float(r["dwpf"]), float(r["alti"])))
        rows.append((int(v[:4]), day, hour, (float(r["tmpf"]) - 32.0) / 1.8, rho))
    return np.array(rows) if rows else np.zeros((0, 5))


def density_table(hours=range(7, 19)):
    """KTUS-derived density at TIMPA (667 m) by local hour: n, P10, P50, P90, mean [kg/m3], T P50 [C]."""
    o = _thp_obs()
    out = {}
    for h in hours:
        x = o[o[:, 2] == h]
        if len(x) == 0:
            continue
        out[int(h)] = {"n": int(len(x)), "p10": float(np.percentile(x[:, 4], 10)), "p50": float(np.percentile(x[:, 4], 50)),
                       "p90": float(np.percentile(x[:, 4], 90)), "mean": float(x[:, 4].mean()),
                       "t_p50_c": float(np.percentile(x[:, 3], 50))}
    return out


RUNWAY_DEG = None    # TIMPA runway heading is not in the repo; rules 3.3.3 say the course is oriented to the wind


def day_conditions(n, seed, hour=None):
    """Mid-April TIMPA conditions per draw: hour, rho [kg/m3], wind, gust [m/s], xwind_deg, temp_c.

    v1: rho and temp_c are resampled from the 2,876 KTUS hourly observations (15-18 Apr 1996-2025, same
    hour when `hour` is given), with density by the proposal's \\nRho method at 667 m; wind, gust and
    direction from the IEM hourly observations (RYN + AVQ + TUS). Density and wind are drawn
    independently (v1 does not model their small correlation). xwind_deg: the rules orient the course
    to the wind (rules 3.3.3), so the residual angle is drawn |N(0, 30 deg)| capped at 90 (estimate).
    """
    rng = np.random.default_rng(seed)
    obs = _wind_obs()
    hrs = rng.integers(7, 19, size=n) if hour is None else _bcast(hour, n, int)
    wind = np.empty(n); gust = np.empty(n); drct = np.empty(n)
    for h in np.unique(hrs):
        sel = obs[obs[:, 0] == h]
        idx = np.where(hrs == h)[0]
        pick = sel[rng.integers(0, len(sel), size=len(idx))]
        wind[idx], gust[idx], drct[idx] = pick[:, 1], pick[:, 2], pick[:, 3]
    gust = np.where(np.isfinite(gust), gust, wind)
    thp = _thp_obs()
    if len(thp):
        rho = np.empty(n); temp = np.empty(n)
        for h in np.unique(hrs):
            sel = thp[thp[:, 2] == h]
            idx = np.where(hrs == h)[0]
            pick = sel[rng.integers(0, len(sel), size=len(idx))]
            rho[idx], temp[idx] = pick[:, 4], pick[:, 3]
    else:   # fallback (v0 diurnal model) when the KTUS file is absent
        frac = np.clip((hrs - 7) / 8.0, 0, 1)
        rho = 1.125 - 0.055 * frac + 0.012 * rng.standard_normal(n)
        temp = 15.0 + 13.0 * frac
    if RUNWAY_DEG is None:
        xdeg = np.minimum(np.abs(rng.normal(0.0, 30.0, n)), 90.0)
    else:
        xdeg = np.abs(((drct - RUNWAY_DEG + 90) % 180) - 90)
    return {"hour": hrs, "rho": rho, "wind": wind, "gust": gust, "xwind_deg": xdeg, "temp_c": temp}


def crosswind(wind, angle_deg):
    return np.asarray(wind) * np.sin(np.radians(angle_deg))


def lap_time_wind_factor(V, wind, r_turn, along=1.0, g=9.80665):
    """Lap time in wind / lap time in still air, same airspeed V and turn radius r_turn.

    Course (rules 3.3.3): 304.8 m upwind and 304.8 m downwind of straights per lap, two 180 deg
    turns and one 360 deg turn (on the downwind leg). `along` = cos(wind angle to the course).
    Turn drift: during each turn the aircraft drifts downwind by w_a*t_turn; the drift of the
    upwind-end 180 and of the 360 shortens the downwind straight, the drift of the downwind-end
    180 lengthens the upwind straight. Crosswind costs crab: ground speed sqrt(V^2 - w_c^2).
    """
    V, w = np.asarray(V, float), np.asarray(wind, float)
    wa = w * along
    wc = w * np.sqrt(np.clip(1 - along * along, 0, 1))
    vg = np.sqrt(np.clip(V * V - wc * wc, 1e-6, None))
    t180 = math.pi * np.asarray(r_turn) / V
    t360 = 2 * t180
    half = 304.8
    t_up = (half + wa * t180) / np.clip(vg - wa, 1e-3, None)
    t_dn = np.clip(half - wa * (t180 + t360), 0, None) / (vg + wa)
    t_wind = t_up + t_dn + 2 * t180 + t360
    t_calm = 2 * half / V + 2 * t180 + t360
    return t_wind / t_calm
