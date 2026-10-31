# Copyright © 2026 Badr Obtel. All rights reserved.
"""Run Scripts 1-2 end to end (TOOLING): tables to the terminal, figures to
analysis/out/.

    python analysis/run_all.py

Uses your functions in s1_course.py and s2_scoring.py and the inputs in
analysis/inputs/. Anything not written yet, or a target still nan, is reported
and skipped; nothing is invented to fill a gap.
"""
import math

import common
import s1_course as s1
import s2_scoring as s2
from common import G0, RULES, SCENARIOS

MISSIONS = RULES["missions"]


class Missing(Exception):
    """A target is nan or a function is not written yet."""


def need(params, *keys):
    absent = [k for k in keys if not common.is_set(params.get(k))]
    if absent:
        raise Missing("set " + ", ".join(absent) + " in aircraft.toml")
    return [params[k] for k in keys]


def attempt(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except NotImplementedError:
        raise Missing(f"not written yet: {fn.__module__}.{fn.__name__}") from None


def floor_table():
    print("Script 1  lap-time floor (constant speed, still air, no overshoot)")
    print("  bank   n      V* m/s   t_min s   r(V*) m")
    for bank in (60.0, 63.0, 65.0, 68.0, 70.0, 72.0, 75.0):
        n = attempt(s1.load_factor, bank)
        v = attempt(s1.best_speed, bank, G0)
        t = attempt(s1.min_lap_time, bank, G0)
        r = attempt(s1.turn_radius, v, bank, G0)
        print(f"  {bank:4.0f}  {n:5.2f}  {v:8.2f}  {t:8.2f}  {r:8.2f}")


def performance(p):
    """Script 1 results for one aircraft's targets."""
    v, bank, os_ = need(p, "v_race_mps", "bank_deg", "marker_overshoot_m")
    v_lof, a_g, a_air = need(p, "v_lof_mps", "a_ground_mps2", "a_air_mps2")
    lap = attempt(s1.lap_length, attempt(s1.turn_radius, v, bank, G0), overshoot=os_)
    t_lap = lap / v
    t_to, x_to = attempt(s1.takeoff_segment, v_lof, a_g, v, a_air)
    out = {"lap_m": lap, "t_lap": t_lap, "n": attempt(s1.load_factor, bank),
           "t_m1": attempt(s1.mission_time, t_to, x_to, lap, v, MISSIONS["m1_laps"]),
           "t_m2": attempt(s1.mission_time, t_to, x_to, lap, v, MISSIONS["m2_laps"])}
    v_tow, t_stow = need(p, "v_tow_mps", "t_stow_s")
    lap_tow = attempt(s1.lap_length, attempt(s1.turn_radius, v_tow, bank, G0), overshoot=os_)
    t_to3, x_to3 = attempt(s1.takeoff_segment, v_lof, a_g, v_tow, a_air)
    t_first = attempt(s1.mission_time, t_to3, x_to3, lap_tow, v_tow, 1)
    out["m3_laps"] = attempt(s1.laps_in_window, t_first, lap_tow / v_tow, MISSIONS["window_s"],
                             t_stow, p["stow_counts_in_window"])
    return out


def completion(perf):
    """Which missions the targets complete. GM survival is not modelled yet
    (Script 5 and TC-02), so GM counts as completed."""
    window = MISSIONS["window_s"]
    done = {"M2": perf["t_m2"] <= window,
            "M3": perf["m3_laps"] >= MISSIONS["m3_min_laps"], "GM": True}
    done["M1"] = perf["t_m1"] <= window or done["M2"]   # a successful M2 also credits M1
    return done


def scores(p, perf, scenario):
    """Script 2 results for one aircraft's targets in one competitor scenario."""
    n_sim, m_c, m_max, m_m3, h = need(p, "n_sim", "m_container_kg", "m_sensor_max_kg",
                                      "m_sensor_m3_kg", "h_drop_m")
    field = common.field_maxima(scenario)
    done = completion(perf)
    w = attempt(s2.m2_payload_mass, n_sim, m_c, m_max)
    h_decl = attempt(s2.declared_drop_height, h)
    parts = {"M1": attempt(s2.m1, done["M1"]),
             "M2": attempt(s2.m2, w, perf["t_m2"], field["m2"], completed=done["M2"]),
             "M3": attempt(s2.m3, perf["m3_laps"], m_m3, field["m3"], completed=done["M3"]),
             "GM": attempt(s2.gm, m_max, h_decl, field["gm"], completed=done["GM"])}
    parts["total"] = attempt(s2.total_mission, *parts.values())
    return {"payload_kg": w, "h_declared_m": h_decl, **parts}


def main():
    print(f"g = {G0} m/s^2; window {MISSIONS['window_s']:.0f} s; "
          f"straights {RULES['course']['straights_per_lap_m']} m per lap\n")
    try:
        floor_table()
    except Missing as e:
        print(f"  ({e})")

    print("\nCompetitor field maxima (competitor.toml; per-mission specialists)")
    print("  scenario       M2 W/t kg/s   M3 N*Ws kg*laps   GM Ws*h kg*m")
    for sc in SCENARIOS:
        f = common.field_maxima(sc)
        print(f"  {sc:<13}  {f['m2']:11.5f}   {f['m3']:15.2f}   {f['gm']:12.3f}")

    totals = {}
    for key in ("a01", "a02"):
        p = common.aircraft(key)
        print(f"\n{p['name']}")
        try:
            perf = performance(p)
            print(f"  lap {perf['lap_m']:.1f} m in {perf['t_lap']:.2f} s (n = {perf['n']:.2f}); "
                  f"M1 3 laps {perf['t_m1']:.2f} s; M2 5 laps {perf['t_m2']:.2f} s; "
                  f"M3 {perf['m3_laps']:.0f} laps (stow counts: {p['stow_counts_in_window']})")
            failed = [m for m, ok in completion(perf).items() if not ok]
            if failed:
                print(f"  NOT COMPLETED with these targets: {', '.join(failed)} (scores 0)")
            for sc in SCENARIOS:
                s = scores(p, perf, sc)
                totals[(key, sc)] = s["total"]
                print(f"  {sc:<13} M1 {s['M1']:.2f}  M2 {s['M2']:.3f}  M3 {s['M3']:.3f}  "
                      f"GM {s['GM']:.3f}  total {s['total']:.3f} / 7.50  "
                      f"(W {s['payload_kg']:.2f} kg, h {s['h_declared_m']:.4f} m)")
        except Missing as e:
            print(f"  ({e})")

    if all((k, sc) in totals for k in ("a01", "a02") for sc in SCENARIOS):
        leaders = {sc: max(("a01", "a02"), key=lambda k: totals[(k, sc)]) for sc in SCENARIOS}
        same = len(set(leaders.values())) == 1
        print("\n01 vs 02: leader " + ", ".join(f"{sc} {k}" for sc, k in leaders.items())
              + ("  -> holds in all three scenarios" if same else "  -> DOES NOT HOLD"))

    import figures
    shared = common.aircraft("a01")      # stow time and the stow assumption
    print()
    for make, args in ((figures.lap_time_vs_speed, ()),
                       (figures.m3_staircase, (shared["t_stow_s"], shared["stow_counts_in_window"]))):
        try:
            print(f"wrote {make(s1, *args).relative_to(common.REPO)}")
        except NotImplementedError:
            print(f"{make.__name__}: waits for your Script 1 functions")


if __name__ == "__main__":
    main()
