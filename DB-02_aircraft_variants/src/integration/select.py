"""Gates and shortlist from the integrated screen (orchestrator, 30 Oct 2026), per the pre-registered rule
(brief/00_BRIEF.md section 9). Reads W/out/integration/screen.json, writes W/out/integration/shortlist.json.

Gates: container inside the 381 mm envelope (the one compliance row the search varies); P(M2 and M3 completed)
>= 0.90 x the best candidate's; P10 total >= the DB-01 control's P10 on the same draws.
Shortlist for the finalists (re-scored with the reliability-aware declaration, five stress scenarios):
  the five gated leaders by P(top); the best gated design of each flap type; the best gated twin (the only frozen-item
  alternative the search can score, for the B clause); the slotted 8S / 6 kg wing at 1.0 to 1.2 m2 and the Fowler
  8S / 6 kg wing at 0.9 and 1.0 m2 (the area question the 30 Oct review raised); rev A's A8 (Fowler, 3-8 kg).
Run: PYTHONDONTWRITEBYTECODE=1 python src/integration/select.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[2]
OUT = W / "out" / "integration"
CX = {"plain": 0, "slotted": 1, "fowler": 2}


def complexity(d):
    """Lower is simpler: flap mechanism, then motor count (rule: the lower-complexity candidate wins a tie)."""
    return CX[d["flap"]] + (2 if d["prop"] == "twin" else 0)


def gates(rows, ctrl):
    best_m3 = max(r["p_m3_done"] for r in rows)
    out = []
    for r in rows:
        g = {"g_381": bool(r.get("ok_381", True)), "g_complete": r["p_m3_done"] >= 0.90 * best_m3,
             "g_p10": r["p10"] >= ctrl["p10"] - 1e-9}
        out.append({**r, **g, "gated": all(g.values()), "complete_need": 0.90 * best_m3, "p10_need": ctrl["p10"]})
    return out


def key(d):
    return (d["s"], d["flap"], d["m_hi"], d["prop"])


def main():
    rows = json.loads((OUT / "screen.json").read_text(encoding="utf-8"))
    ctrl = next(r for r in rows if r["id"].startswith("CONTROL"))
    G = gates([r for r in rows if not r["id"].startswith("CONTROL")], ctrl)
    gated = sorted([r for r in G if r["gated"]], key=lambda r: -r["p_mission_top"])
    pick = {}

    def add(r, why):
        if r is not None:
            pick.setdefault(key(r), {"s": r["s"], "flap": r["flap"], "m_hi": r["m_hi"], "prop": r["prop"], "why": []})
            pick[key(r)]["why"].append(why)

    for r in gated[:5]:
        add(r, "gated leader")
    for f in ("plain", "slotted", "fowler"):
        add(next((r for r in gated if r["flap"] == f), None), f"best gated {f}")
    tw = next((r for r in gated if r["prop"] == "twin"), None)
    if tw is None:                       # no twin passes: still test the B clause's only frozen-item alternative
        tw = max((r for r in G if r["prop"] == "twin"), key=lambda r: r["p_mission_top"])
        add(tw, "best twin (fails the gates; frozen-item test for B)")
    else:
        add(tw, "best gated twin")
    byk = {key(r): r for r in G}
    for k, why in (((1.0, "slotted", 6.0, "8s"), "B-area sweep"), ((1.1, "slotted", 6.0, "8s"), "B-area sweep"),
                   ((1.2, "slotted", 6.0, "8s"), "B-area sweep"), ((0.9, "fowler", 6.0, "8s"), "rev A Variant A"),
                   ((1.0, "fowler", 6.0, "8s"), "A-area check"), ((0.9, "fowler", 8.0, "8s"), "rev A A8")):
        add(byk.get(k), why)
    short = []
    for k, d in pick.items():
        r = byk[k]
        short.append({**d, "id": r["id"], "gated": r["gated"], "complexity": complexity(r),
                      "screen_p_top": r["p_mission_top"], "screen_mean": r["mean"], "screen_p10": r["p10"],
                      "screen_p_m3_done": r["p_m3_done"]})
    short.sort(key=lambda d: -d["screen_p_top"])
    res = {"control": {k: ctrl[k] for k in ("mean", "p10", "p_mission_top", "p_m3_done")},
           "gate_complete_need": G[0]["complete_need"], "gate_p10_need": ctrl["p10"],
           "n_designs": len(G), "n_gated": len(gated),
           "gated_top10": [{k: r[k] for k in ("id", "p_mission_top", "p_mission_top_ci95", "mean", "p10", "p_m3_done")}
                           for r in gated[:10]],
           "failed_leaders": [{k: r[k] for k in ("id", "p_mission_top", "p10", "p_m3_done", "g_381", "g_complete", "g_p10")}
                              for r in sorted(G, key=lambda r: -r["p_mission_top"])[:12] if not r["gated"]],
           "shortlist": short}
    (OUT / "shortlist.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"{len(gated)}/{len(G)} gated; complete >= {res['gate_complete_need']:.3f}, p10 >= {ctrl['p10']:.3f}")
    for r in res["gated_top10"]:
        print(f"  {r['id']:26s} P(top) {r['p_mission_top']:.3f} [{r['p_mission_top_ci95'][0]:.3f}, {r['p_mission_top_ci95'][1]:.3f}] "
              f"mean {r['mean']:.3f} p10 {r['p10']:.2f} pM3 {r['p_m3_done']:.2f}")
    print("failed leaders:", [(r["id"], round(r["p_mission_top"], 3)) for r in res["failed_leaders"][:6]])
    print("shortlist:", [(d["id"], d["why"]) for d in short])
    return res


if __name__ == "__main__":
    main()
