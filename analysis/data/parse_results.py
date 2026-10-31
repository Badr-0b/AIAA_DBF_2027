# Copyright © 2026 Badr Obtel. All rights reserved.
"""Every team's published scores, 2022-2026, from the AIAA competition
summaries (TOOLING).

    python analysis/data/parse_results.py

Reads raw/aiaa-dbf-<year>-results.pdf (fetch.py) in content-stream order
(pdftotext -raw keeps each table row on one line) and writes
dbf_results.csv: one row per team per year, with the verbatim source line.

Each row is accepted only if the published numbers agree with each other:
  1. GM + M1 + M2 + M3 = Total mission score (within 0.02, the 2-decimal rounding)
  2. Report x Total + Participation = Competition score (within 0.6)
  3. 2025-26 only: 0.15 Proposal + 0.85 Design = Report total (within 0.09:
     the table prints the proposal score as a whole number, worth up to 0.075)
2022 printed no participation column and its scores show none was added.
Rows that fail stay in the file with check = the failed test, never silently.
"""
import csv
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "dbf_results.csv"

# Trailing numeric columns per year, after "rank [queue] name".
LAYOUT = {
    2026: ("p", "gm", "m1", "m2", "m3", "total", "proposal", "design", "report", "score"),
    2025: ("p", "gm", "m1", "m2", "m3", "total", "proposal", "design", "report", "score"),
    2024: ("p", "gm", "m1", "m2", "m3", "total", "report", "score"),
    2023: ("p", "gm", "m1", "m2", "m3", "total", "report", "score"),
    2022: ("gm", "m1", "m2", "m3", "total", "report", "score"),
}
QUEUE = {2024, 2023, 2022}          # a queue / flight-order number follows the rank
NUM = re.compile(r"^-?\d+(\.\d+)?$")


def rows(year):
    text = subprocess.run(["pdftotext", "-raw", "-enc", "UTF-8",
                           str(RAW / f"aiaa-dbf-{year}-results.pdf"), "-"],
                          capture_output=True, text=True, encoding="utf-8").stdout
    cols = LAYOUT[year]
    for line in text.splitlines():
        tok = line.split()
        if len(tok) < 3 or not tok[0].isdigit():
            continue
        tail = []
        while tok and NUM.match(tok[-1]):
            tail.insert(0, tok.pop())
        head = tok[1:]                                  # drop the rank
        if year in QUEUE and head and head[0].isdigit():
            head = head[1:]
        name = " ".join(head)
        if not name or len(tail) == 0:
            continue
        yield int(tok[0]), name, tail, cols, line.strip()


def check(year, rec):
    f = {k: float(v) for k, v in rec.items() if k in LAYOUT[year] and v != ""}
    problems = []
    if all(k in f for k in ("gm", "m1", "m2", "m3", "total")):
        if abs(f["gm"] + f["m1"] + f["m2"] + f["m3"] - f["total"]) > 0.02:
            problems.append("mission sum")
    if all(k in f for k in ("total", "report", "score")):
        part = f.get("p", 0.0)          # 2022: no participation term
        if abs(f["report"] * f["total"] + part - f["score"]) > 0.6:
            problems.append("score formula")
    if all(k in f for k in ("proposal", "design", "report")):
        if abs(0.15 * f["proposal"] + 0.85 * f["design"] - f["report"]) > 0.09:
            problems.append("report weights")
    return "ok" if not problems else "FLAG: " + ", ".join(problems)


def main():
    fields = ["year", "rank", "team", "p", "gm", "m1", "m2", "m3", "total",
              "proposal", "design", "report", "score", "check", "source_id", "quote"]
    out, summary = [], {}
    for year in sorted(LAYOUT, reverse=True):
        seen = set()
        for rank, name, tail, cols, line in rows(year):
            if rank in seen:            # the summary repeats the podium on the last page
                continue
            rec = {"year": year, "rank": rank, "team": name}
            if len(tail) == len(cols):
                rec.update(dict(zip(cols, tail)))
            else:                       # short row (blank cells): keep the raw line only
                rec.update({c: "" for c in cols})
            rec["check"] = check(year, rec) if len(tail) == len(cols) else \
                f"FLAG: {len(tail)} of {len(cols)} numbers"
            rec["source_id"] = f"aiaa-dbf-{year}-results"
            rec["quote"] = line
            seen.add(rank)
            out.append(rec)
        n = [r for r in out if r["year"] == year]
        summary[year] = (len(n), sum(r["check"] == "ok" for r in n))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    for year, (n, ok) in summary.items():
        print(f"{year}: {n} teams parsed, {ok} pass all checks, {n - ok} flagged")


if __name__ == "__main__":
    main()
