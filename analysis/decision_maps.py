# Copyright © 2026 Badr Obtel. All rights reserved.
"""Rough decision maps from the scoring model and the competitor scenarios
(TOOLING; first step of Script 6).

    python analysis/decision_maps.py

  out/map_m2.pdf  M2 score over payload x five-lap time (expected scenario),
                  with the 2025 weight/time evidence converted to five laps
  out/map_gm.pdf  GM score against the declared sensor mass at 1.524 m, all
                  three scenarios
Every input: inputs/*.toml and data/dbf_aircraft.csv (verified).
"""
import csv
import sys
from pathlib import Path

import numpy as np

import common
import s2_scoring as s2
from common import OUT, SCENARIOS

sys.path.insert(0, str(common.REPO / "design-system" / "matplotlib"))
import dbfplot as dp  # noqa: E402


def evidence_2025():
    """2025 weight/time points (payload kg, 5-lap s), from the verified dataset."""
    rows = list(csv.DictReader((common.ANALYSIS / "data" / "dbf_aircraft.csv").open(encoding="utf-8")))
    c = common.load("competitor")["m2"]

    def val(team, param, kind):
        hit = [float(r["value_si"]) for r in rows if r["team"] == team and r["year"] == "2025"
               and r["param"] == param and r["mission"] == "M2" and r["kind"] == kind]
        return hit[0] if hit else None
    pts = []
    for team, short, kind in (("Embry-Riddle Aeronautical University, Daytona Beach", "ERAU 25 MEAS", "measured"),
                              ("Embry-Riddle Aeronautical University, Daytona Beach", "ERAU 25 PRED", "predicted"),
                              ("University of New South Wales", "UNSW 25 PRED", "predicted"),
                              ("University of California, Los Angeles", "UCLA 25 PRED", "predicted")):
        w, t3 = val(team, "payload_mass", kind), val(team, "mission_time", kind)
        lap = val(team, "lap_time", kind) or c["lap_s"] * t3 / c["three_lap_s"]
        if w and t3:
            pts.append((short, w, t3 + 2 * lap, kind))
    return pts


def map_m2():
    field = common.field_maxima("expected")["m2"]
    w = np.linspace(1.0, 17.0, 161)
    t = np.linspace(110.0, 280.0, 171)
    W, T = np.meshgrid(w, t)
    Z = np.vectorize(lambda ww, tt: s2.m2(ww, tt, field))(W, T)
    dp.use()
    fig, ax = dp.figure("col", 2.4)
    cs = ax.contour(W, T, Z, levels=[1.2, 1.4, 1.6, 1.8, 1.95], colors=dp.STEEL, linewidths=0.6)
    ax.clabel(cs, fmt=lambda v: f"M2 {v:.2f}", fontsize=4.8)
    for sc, ls in zip(SCENARIOS, ("-", "--", ":")):
        rate = common.field_maxima(sc)["m2"]
        ax.plot(w, w / rate, color=dp.INK, lw=0.9, ls=ls, label=f"MAX {sc[:4].upper()}.")
    for name, pw, pt, kind in evidence_2025():
        ax.plot(pw, pt, "o", ms=3.4, color=dp.INK if kind == "measured" else "white", mec=dp.INK, mew=0.8)
        ax.annotate(name, (pw, pt), xytext=(4, 2), textcoords="offset points", fontsize=4.8,
                    family=dp.MONO, color=dp.INK)
    ax.set_xlim(1, 17)
    ax.set_ylim(110, 280)
    ax.set_xlabel("M2 payload, container + simulators (kg)")
    ax.set_ylabel("Five-lap time from throttle-up (s)")
    leg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=4.8,
                    title="FIELD MAX W/t, FIVE LAPS", title_fontsize=4.8)
    for tx in leg.get_texts():
        tx.set_family(dp.MONO)
    leg.get_title().set_family(dp.MONO)
    dp.save(fig, OUT / "map_m2.pdf")


def map_gm():
    h = s2.declared_drop_height(common.RULES["ground"]["drop_height_max_m"])
    ws = np.linspace(0.2, 10.0, 197)
    dp.use()
    fig, ax = dp.figure("col", 2.0)
    for sc, ls in zip(SCENARIOS, ("-", "--", ":")):
        field = common.field_maxima(sc)["gm"]
        ax.plot(ws, [s2.gm(x, h, field) for x in ws], color=dp.INK, ls=ls, lw=1.0, label=sc.upper())
    ax.set_xlim(0, 10)
    ax.set_ylim(0.5, 1.55)
    ax.set_xlabel("Declared maximum sensor mass (kg), drop height 1.524 m")
    ax.set_ylabel("GM score")
    leg = ax.legend(loc="lower right", fontsize=5.2)
    for tx in leg.get_texts():
        tx.set_family(dp.MONO)
    dp.save(fig, OUT / "map_gm.pdf")


def main():
    OUT.mkdir(exist_ok=True)
    map_m2()
    map_gm()
    field = common.field_maxima("expected")
    print("M2 payload (kg) needed for a given score, expected field (5-lap time 160 / 190 / 220 s):")
    for target in (1.4, 1.6, 1.8, 2.0):
        need = [(target - 1) * field["m2"] * t for t in (160, 190, 220)]
        print(f"  M2 {target:.1f}: " + " / ".join(f"{x:5.1f}" for x in need))
    h = s2.declared_drop_height(common.RULES["ground"]["drop_height_max_m"])
    print("GM score vs declared sensor mass at 1.524 m (aggressive / expected / conservative):")
    for m in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
        print(f"  {m:4.1f} kg: " + " / ".join(f"{s2.gm(m, h, common.field_maxima(sc)['gm']):.2f}" for sc in SCENARIOS))
    print("2025 evidence at five laps:", [(n, round(w, 2), round(t)) for n, w, t, _ in evidence_2025()])


if __name__ == "__main__":
    main()
