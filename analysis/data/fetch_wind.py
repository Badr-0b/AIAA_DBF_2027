# Copyright © 2026 Badr Obtel. All rights reserved.
"""Mid-April wind at the fly-off site from 30 years of ASOS reports (TOOLING).

    python analysis/data/fetch_wind.py

Source: Iowa Environmental Mesonet (IEM), ASOS/AWOS archive, routine hourly
reports, https://mesonet.agron.iastate.edu/request/download.phtml (the same
archive behind the verified air-density value, \\nRho). Stations around TIMPA
(32.26474 N, 111.27386 W): RYN Ryan Airfield (~16 km), AVQ Marana Regional
(~17 km), TUS Tucson International (~35 km). Window: 15-18 April 1996-2025
(the fly-off dates, rules Sec. 2.5), flying hours 07:00-18:00 local (Arizona
does not observe DST, so America/Phoenix = MST all year).

Writes raw/iem_<station>_apr.csv (as downloaded), wind_timpa.csv (summary)
and analysis/out/wind_timpa.pdf.
"""
import csv
import io
import statistics as st
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "design-system" / "matplotlib"))
KT = 0.514444   # m/s per knot (exact: 1852/3600)
URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st}&data=sknt&data=drct"
       "&data=gust&year1={y}&month1=4&day1=15&year2={y}&month2=4&day2=19&tz=America%2FPhoenix"
       "&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=3")
STATIONS = {"RYN": "Ryan Airfield", "AVQ": "Marana Regional", "TUS": "Tucson International"}
YEARS = range(1996, 2026)


def fetch(station):
    out = RAW / f"iem_{station}_apr.csv"
    if out.exists():
        return out
    rows, header = [], None
    for y in YEARS:
        with urllib.request.urlopen(URL.format(st=station, y=y), timeout=60) as r:
            text = r.read().decode("utf-8")
        lines = text.strip().splitlines()
        if not lines:
            continue
        header = lines[0]
        rows += lines[1:]
        time.sleep(0.5)   # be polite to the IEM server
    out.write_text("\n".join([header or "station,valid,sknt,drct,gust"] + rows) + "\n", encoding="utf-8")
    return out


def load(path):
    obs = []
    for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))):
        hour = int(r["valid"][11:13])
        if not 7 <= hour <= 18 or r["sknt"] in ("M", ""):
            continue
        gust = float(r["gust"]) * KT if r["gust"] not in ("M", "") else None
        obs.append({"year": int(r["valid"][:4]), "hour": hour, "speed": float(r["sknt"]) * KT, "gust": gust})
    return obs


def summary(obs):
    v = sorted(o["speed"] for o in obs)
    q = st.quantiles(v, n=20)
    gusts = [o["gust"] for o in obs if o["gust"] is not None]
    return {"n": len(v), "years": len({o["year"] for o in obs}), "mean": st.mean(v), "median": st.median(v),
            "p75": q[14], "p90": q[17], "p95": q[18], "max": v[-1],
            "share_calm": sum(x < 0.5 for x in v) / len(v),
            "share_gt_7_5": sum(x > 7.5 for x in v) / len(v),
            "gust_reports": len(gusts), "gust_p90": st.quantiles(gusts, n=10)[8] if len(gusts) > 10 else None}


def main():
    import dbfplot as dp
    from common import OUT
    stats = {}
    for code in STATIONS:
        path = fetch(code)
        obs = load(path)
        if len(obs) < 100:
            print(f"{code}: only {len(obs)} usable observations, skipped")
            continue
        stats[code] = (summary(obs), obs)
    with (HERE / "wind_timpa.csv").open("w", newline="", encoding="utf-8") as f:
        keys = ["station", "name", "n", "years", "mean", "median", "p75", "p90", "p95", "max",
                "share_calm", "share_gt_7_5", "gust_reports", "gust_p90"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for code, (s, _) in stats.items():
            w.writerow({"station": code, "name": STATIONS[code],
                        **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}})
    for code, (s, _) in stats.items():
        print(f"{code} {STATIONS[code]:22} n={s['n']:5} years={s['years']:2}  mean {s['mean']:.2f}  "
              f"median {s['median']:.2f}  p75 {s['p75']:.2f}  p90 {s['p90']:.2f}  p95 {s['p95']:.2f} m/s  "
              f">7.5 m/s {100 * s['share_gt_7_5']:.0f} %  gust p90 "
              + (f"{s['gust_p90']:.1f}" if s["gust_p90"] else "n/a"))
    dp.use()
    fig, ax = dp.figure("col", 2.0)
    for (code, (s, obs)), colour, ls in zip(stats.items(), (dp.INK, dp.STEEL, dp.FOG), ("-", "--", ":")):
        v = sorted(o["speed"] for o in obs)
        ax.plot(v, [100 * (i + 1) / len(v) for i in range(len(v))], color=colour, ls=ls, lw=1.0,
                label=f"{code} ({s['years']} yr, n={s['n']})")
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Sustained wind, 07-18 h, 15-18 April (m/s)")
    ax.set_ylabel("Observations at or below (%)")
    leg = ax.legend(loc="lower right", fontsize=5.2)
    for t in leg.get_texts():
        t.set_family(dp.MONO)
    dp.save(fig, OUT / "wind_timpa.pdf")


if __name__ == "__main__":
    main()
