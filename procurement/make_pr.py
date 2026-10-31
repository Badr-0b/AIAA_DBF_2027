#!/usr/bin/env python3
"""PR-01 generator: one CSV in, two documents out.

    python make_pr.py            (run by ./build.sh)

Reads pr01_items.csv, the single source of truth, and writes
    build/pr01_totals.tex    totals as macros (glance panel)
    build/pr01_tierA.tex     Tier A tables, one per category
    build/pr01_tierB.tex     Tier B tables, one per category
    build/pr01_sources.tex   reference listings with their URLs
    PR-01_initial_request.xlsx   the same lines for the purchasing office
Standard library only: nothing to install. Edit the CSV, never the outputs.
"""
import csv
import math
import pathlib
import sys
import zipfile
from collections import OrderedDict
from xml.sax.saxutils import escape, quoteattr

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "pr01_items.csv"
BUILD = HERE / "build"
XLSX = HERE / "PR-01_initial_request.xlsx"

# Exchange rates. Change them here (and in the workbook's "Read me" sheet,
# which this script writes from the same values).
USD_PER = {"USD": 1.0, "GBP": 1.3229}   # USD per 1 unit of currency
KWD_PER_USD = 0.310829
RATE_SOURCE = "currencyconvert.online, updated 2026-10-08 21:00 UTC (market rates)"

TIERS = {"A": "Tier A: local purchase this week", "B": "Tier B: formal university request"}
STATUS = {"buy": "Buy now", "hold": "Budget hold"}
BASIS = {"listing": "Listing", "estimate": "Estimate"}
VIA = {"page": "read on the vendor page", "search": "from search results for the vendor page"}
FIELDS = ["id", "tier", "category", "item", "spec", "qty", "unit", "ref_price", "ref_cur",
          "status", "basis", "ref_vendor", "ref_url", "checked", "checked_via", "need_by",
          "budget_row", "supports", "notes"]

# Rows of proposal Table 02 (proposal/sections/02_management_summary.tex) that PR-01
# feeds: budget_row value -> macro written to proposal/data/budget.tex
BUDGET = OrderedDict([("airframe", "bAirframe"), ("propulsion", "bPropulsion"),
                      ("batteries", "bBatteries"), ("sensor", "bSensor"),
                      ("containers", "bContainers"), ("consumables", "bConsumables"),
                      ("crating", "bCrating")])
PROPOSAL_BUDGET = HERE.parent / "proposal" / "data" / "budget.tex"
FLYOFF_FEE = 550    # USD per team, rules §2.6
AIAA_DUES = 37      # USD per student member per year, aiaa.org dues page, checked 2026-10-09


# --------------------------------------------------------------------------
# Read and validate
# --------------------------------------------------------------------------
def load():
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    errors, seen = [], set()
    for n, r in enumerate(rows, start=2):
        where = f"{SRC.name} line {n} ({r.get('id', '?')})"
        missing = [k for k in FIELDS if k not in r]
        if missing:
            sys.exit(f"{SRC.name}: missing columns {missing}")
        if r["id"] in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(r["id"])
        if r["tier"] not in TIERS:
            errors.append(f"{where}: tier must be A or B")
        if r["status"] not in STATUS:
            errors.append(f"{where}: status must be buy or hold")
        if r["basis"] not in BASIS:
            errors.append(f"{where}: basis must be listing or estimate")
        if r["ref_cur"] not in USD_PER:
            errors.append(f"{where}: unknown currency {r['ref_cur']}")
        if r["basis"] == "listing" and not (r["ref_vendor"] and r["ref_url"]):
            errors.append(f"{where}: a listing needs ref_vendor and ref_url")
        if r["basis"] == "listing" and r["checked_via"] not in VIA:
            errors.append(f"{where}: a listing needs checked_via = page or search")
        if r["budget_row"] not in BUDGET:
            errors.append(f"{where}: budget_row must be one of {', '.join(BUDGET)}")
        try:
            r["qty"] = int(r["qty"])
            r["ref_price"] = float(r["ref_price"])
            assert r["qty"] > 0 and r["ref_price"] >= 0
        except (ValueError, AssertionError):
            errors.append(f"{where}: qty must be a positive integer and ref_price a number")
            continue
        r["unit_usd"] = r["ref_price"] * USD_PER.get(r["ref_cur"], 1.0)
        r["ext_usd"] = r["qty"] * r["unit_usd"]
    if errors:
        sys.exit("\n".join(errors))
    return rows


def totals(rows):
    t = {"A": 0.0, "Bbuy": 0.0, "Bhold": 0.0, "listed": 0.0}
    for r in rows:
        key = "A" if r["tier"] == "A" else ("Bbuy" if r["status"] == "buy" else "Bhold")
        t[key] += r["ext_usd"]
        if r["basis"] == "listing":
            t["listed"] += r["ext_usd"]
    t["B"] = t["Bbuy"] + t["Bhold"]
    t["all"] = t["A"] + t["B"]
    return t


# --------------------------------------------------------------------------
# LaTeX
# --------------------------------------------------------------------------
TEX_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}", "≤": r"$\leq$", "≥": r"$\geq$"}


def tex(s):
    return "".join(TEX_ESC.get(c, c) for c in s)


def money(x):
    return f"{x:,.2f}"


def by_category(rows, tier):
    groups = OrderedDict()
    for r in rows:
        if r["tier"] == tier:
            groups.setdefault(r["category"], []).append(r)
    return groups


def tier_tables(rows, tier):
    out = []
    for cat, items in by_category(rows, tier).items():
        sub = sum(r["ext_usd"] for r in items)
        out.append(r"\par\addvspace{6pt}\needspace{1.4in}\noindent")
        out.append(r"\captionof{table}{%s. %d %s, subtotal US\$%s.}\nopagebreak"
                   % (tex(cat), len(items), "line" if len(items) == 1 else "lines", money(sub)))
        out.append(r"\begin{dbflongtable}{colspec={Q[l,wd=0.34in] X[l] Q[r,wd=0.3in] "
                   r"Q[r,wd=0.62in] Q[r,wd=0.68in] Q[l,wd=0.62in]}, "
                   r"row{Z}={font=\dbftotalrow}, hline{Y}={0.4pt,dbfGraphite}}")
        out.append(r"ID & Item and specification & Qty & Unit, USD & Ext., USD & Status \\")
        for i, r in enumerate(items):
            # \\* on the last item keeps the subtotal from starting a page alone
            eol = r"\\*" if i == len(items) - 1 else r"\\"
            detail = tex(r["spec"])
            extra = " ".join(x for x in (("Ref. " + r["supports"] + ".") if r["supports"] else "",
                                         r["notes"]) if x)
            cell = r"{\textbf{%s}\\{\footnotesize %s}" % (tex(r["item"]), detail)
            if extra:
                cell += r"\\{\footnotesize\color{dbfSteel}%s}" % tex(extra)
            cell += "}"
            status = r"{{\dbfmono %s}\\{\scriptsize\color{dbfSteel}%s}}" % (
                "BUY" if r["status"] == "buy" else "HOLD", BASIS[r["basis"]].lower())
            unit = money(r["unit_usd"])
            if r["ref_cur"] != "USD":
                unit = r"{%s\\{\scriptsize\color{dbfSteel}%s %s}}" % (unit, r["ref_cur"], money(r["ref_price"]))
            out.append(r"{\dbfmono %s} & %s & %d & %s & %s & %s %s"
                       % (r["id"], cell, r["qty"], unit, money(r["ext_usd"]), status, eol))
        out.append(r" & Subtotal & & & %s & \\" % money(sub))
        out.append(r"\end{dbflongtable}")
        out.append(r"\par\vspace{6pt}")
    return "\n".join(out) + "\n"


def sources_list(rows):
    out = [r"\begin{itemize}"]
    for r in rows:
        if r["basis"] != "listing":
            continue
        price = f"US\\${money(r['ref_price'])}" if r["ref_cur"] == "USD" else \
            f"{r['ref_cur']} {money(r['ref_price'])} (US\\${money(r['unit_usd'])})"
        out.append(r"\item {\dbfmono %s}\enspace %s: %s, %s, checked %s, %s.\\ \url{%s}"
                   % (r["id"], tex(r["item"]), tex(r["ref_vendor"]), price, r["checked"],
                      VIA[r["checked_via"]], r["ref_url"]))
    out.append(r"\end{itemize}")
    return "\n".join(out) + "\n"


def write_tex(rows, t):
    BUILD.mkdir(exist_ok=True)
    n_listed = sum(1 for r in rows if r["basis"] == "listing")
    macros = {
        "prTotalA": money(t["A"]), "prTotalBbuy": money(t["Bbuy"]), "prTotalBhold": money(t["Bhold"]),
        "prTotalB": money(t["B"]), "prTotal": money(t["all"]),
        "prTotalKWD": f"{t['all'] * KWD_PER_USD:,.0f}", "prLines": str(len(rows)),
        "prLinesA": str(sum(r["tier"] == "A" for r in rows)),
        "prLinesB": str(sum(r["tier"] == "B" for r in rows)),
        "prLinesHold": str(sum(r["status"] == "hold" for r in rows)),
        "prListedLines": str(n_listed),
        "prListedPage": str(sum(r["checked_via"] == "page" for r in rows)),
        "prListedSearch": str(sum(r["checked_via"] == "search" for r in rows)),
        "prListedShare": f"{100 * t['listed'] / t['all']:.0f}",
        "prRateKWD": f"{KWD_PER_USD:.4f}", "prRateGBP": f"{USD_PER['GBP']:.4f}",
        "prFee": f"{FLYOFF_FEE:,}", "prAIAA": f"{AIAA_DUES:,}",
        "prRateSource": tex(RATE_SOURCE),
    }
    head = "% Generated by make_pr.py from pr01_items.csv. Do not edit.\n"
    (BUILD / "pr01_totals.tex").write_text(
        head + "".join(f"\\newcommand\\{k}{{{v}}}\n" for k, v in macros.items()), encoding="utf-8")
    (BUILD / "pr01_tierA.tex").write_text(head + tier_tables(rows, "A"), encoding="utf-8")
    (BUILD / "pr01_tierB.tex").write_text(head + tier_tables(rows, "B"), encoding="utf-8")
    (BUILD / "pr01_sources.tex").write_text(head + sources_list(rows), encoding="utf-8")


def write_budget(rows):
    """Proposal Table 02 rows summed from PR-01, in whole US dollars."""
    sums = OrderedDict((k, 0.0) for k in BUDGET)
    for r in rows:
        sums[r["budget_row"]] += r["ext_usd"]
    rounded = OrderedDict((k, round(v)) for k, v in sums.items())
    lines = [
        "% Generated by procurement/make_pr.py from procurement/pr01_items.csv. Do not edit:",
        "% change the CSV and run procurement/build.sh. US dollars, rounded to whole dollars.",
        "% These are the Table 02 rows that PR-01 covers; travel, contingency and funding are",
        "% team facts and stay in sections/02_management_summary.tex.",
    ]
    lines += [f"\\newcommand\\{BUDGET[k]}{{{v:,}}}" for k, v in rounded.items()]
    lines += [
        f"\\newcommand\\bHardware{{{sum(rounded.values()):,}}}   % sum of the rows above",
        f"\\newcommand\\bFlyoffFee{{{FLYOFF_FEE:,}}}   % per team, rules 2.6",
        f"\\newcommand\\bAIAADues{{{AIAA_DUES:,}}}   % per student member per year, aiaa.org, checked 2026-10-09",
    ]
    PROPOSAL_BUDGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rounded


# --------------------------------------------------------------------------
# XLSX (SpreadsheetML written directly; no third-party package)
# --------------------------------------------------------------------------
INK, GRAPHITE, STEEL, MIST, BONE = "FF0B0C0E", "FF2B2E33", "FF5B616B", "FFE4E6E9", "FFF3F2EE"

# (header, width in characters, cell style)
COLUMNS = [("ID", 6, "mono"), ("Tier", 5, "mono"), ("Category", 16, "wrap"), ("Item", 24, "wrap"),
           ("Specification", 46, "wrap"), ("Qty", 6, "int"), ("Ref. price", 10, "num"),
           ("Cur.", 6, "mono"), ("Unit, USD", 11, "usd"), ("Ext., USD", 12, "usd"),
           ("Unit, KWD", 11, "kwd"), ("Ext., KWD", 12, "kwd"), ("Status", 12, "wrap"),
           ("Price basis", 10, "wrap"), ("Reference vendor", 24, "wrap"), ("Reference URL", 36, "link"),
           ("Checked", 11, "mono"), ("Checked via", 10, "wrap"), ("Need by", 11, "mono"),
           ("For", 18, "wrap"), ("Notes", 40, "note")]
LASTCOL = "U"   # letter of the last column above
STYLE = {"default": 0, "head": 1, "wrap": 2, "mono": 3, "int": 4, "usd": 5, "kwd": 6, "note": 7,
         "link": 8, "tlabel": 9, "tusd": 10, "tkwd": 11, "title": 12, "text": 13, "rate": 14, "num": 15,
         "pct": 16}

STYLES_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="4"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/><numFmt numFmtId="165" formatCode="#,##0.000"/><numFmt numFmtId="166" formatCode="0.000000"/><numFmt numFmtId="167" formatCode="#,##0.00"/></numFmts>
<fonts count="7">
<font><sz val="10"/><color rgb="{INK}"/><name val="Geist"/><family val="2"/></font>
<font><b/><sz val="9"/><color rgb="{GRAPHITE}"/><name val="Geist"/><family val="2"/></font>
<font><sz val="10"/><color rgb="{INK}"/><name val="Geist Mono"/><family val="3"/></font>
<font><sz val="10"/><color rgb="{STEEL}"/><name val="Geist"/><family val="2"/></font>
<font><u/><sz val="10"/><color rgb="{GRAPHITE}"/><name val="Geist"/><family val="2"/></font>
<font><b/><sz val="14"/><color rgb="{INK}"/><name val="Geist"/><family val="2"/></font>
<font><b/><sz val="10"/><color rgb="{INK}"/><name val="Geist Mono"/><family val="3"/></font>
</fonts>
<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="{MIST}"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="{BONE}"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="3"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left/><right/><top/><bottom style="thin"><color rgb="{GRAPHITE}"/></bottom><diagonal/></border>
<border><left/><right/><top style="thin"><color rgb="{INK}"/></top><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="17">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="1" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="164" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="165" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="0" fontId="1" fillId="3" borderId="2" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
<xf numFmtId="164" fontId="6" fillId="3" borderId="2" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
<xf numFmtId="165" fontId="6" fillId="3" borderId="2" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
<xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="166" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="167" fontId="2" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
<xf numFmtId="10" fontId="6" fillId="3" borderId="2" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def col(n):  # 1 -> A
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def c_str(ref, text, style):
    return (f'<c r="{ref}" s="{STYLE[style]}" t="inlineStr"><is><t xml:space="preserve">'
            f"{escape(text)}</t></is></c>")


def c_num(ref, value, style, formula=None):
    f = f"<f>{escape(formula)}</f>" if formula else ""
    return f'<c r="{ref}" s="{STYLE[style]}">{f}<v>{value!r}</v></c>'


def row_height(texts):
    """Excel does not auto-fit wrapped rows on open, so estimate the height."""
    lines = 1
    for text, width in texts:
        per_line = max(width - 1, 1)
        lines = max(lines, sum(math.ceil(max(len(p), 1) / per_line) for p in text.split("\n")))
    return 13.5 * lines + 3


def readme_cell(label):
    """Absolute reference to the rate value next to `label` on the Read me sheet."""
    for k, (kind, payload) in enumerate(README_ROWS, 1):
        if kind == "rate" and payload[0] == label:
            return f"'Read me'!$B${k}"
    raise KeyError(label)


def items_sheet(rows, t):
    rate = readme_cell("USD → KWD")
    gbp = readme_cell("GBP → USD")
    out, links = [], []
    header = "".join(c_str(f"{col(i)}1", h, "head") for i, (h, _, _) in enumerate(COLUMNS, 1))
    out.append(f'<row r="1" ht="28" customHeight="1">{header}</row>')
    for k, r in enumerate(rows, 2):
        unit_f = f"G{k}" if r["ref_cur"] == "USD" else f"G{k}*{gbp}"
        cells = [
            c_str(f"A{k}", r["id"], "mono"), c_str(f"B{k}", r["tier"], "mono"),
            c_str(f"C{k}", r["category"], "wrap"), c_str(f"D{k}", r["item"], "wrap"),
            c_str(f"E{k}", r["spec"], "wrap"), c_num(f"F{k}", r["qty"], "int"),
            c_num(f"G{k}", r["ref_price"], "num"), c_str(f"H{k}", r["ref_cur"], "mono"),
            c_num(f"I{k}", round(r["unit_usd"], 4), "usd", unit_f),
            c_num(f"J{k}", round(r["ext_usd"], 4), "usd", f"F{k}*I{k}"),
            c_num(f"K{k}", round(r["unit_usd"] * KWD_PER_USD, 4), "kwd", f"I{k}*{rate}"),
            c_num(f"L{k}", round(r["ext_usd"] * KWD_PER_USD, 4), "kwd", f"F{k}*K{k}"),
            c_str(f"M{k}", STATUS[r["status"]], "wrap"), c_str(f"N{k}", BASIS[r["basis"]], "wrap"),
            c_str(f"O{k}", r["ref_vendor"], "wrap"),
            c_str(f"P{k}", r["ref_url"], "link") if r["ref_url"] else "",
            c_str(f"Q{k}", r["checked"], "mono"),
            c_str(f"R{k}", {"page": "Vendor page", "search": "Search result"}.get(r["checked_via"], ""), "wrap"),
            c_str(f"S{k}", r["need_by"], "mono"),
            c_str(f"T{k}", r["supports"], "wrap"), c_str(f"U{k}", r["notes"], "note"),
        ]
        if r["ref_url"]:
            links.append((f"P{k}", r["ref_url"]))
        ht = row_height([(r["category"], 16), (r["item"], 24), (r["spec"], 46),
                         (r["ref_vendor"], 24), ("Search result" if r["checked_via"] else "", 10),
                         (r["supports"], 18), (r["notes"], 40)])
        out.append(f'<row r="{k}" ht="{ht:g}" customHeight="1">{"".join(cells)}</row>')

    last = len(rows) + 1
    rng = lambda c: f"${c}$2:${c}${last}"
    k = last + 2
    tot_rows = [
        ("Tier A, local purchase", f'SUMIFS({rng("J")},{rng("B")},"A")', t["A"]),
        ("Tier B, buy now", f'SUMIFS({rng("J")},{rng("B")},"B",{rng("M")},"Buy now")', t["Bbuy"]),
        ("Tier B, budget holds", f'SUMIFS({rng("J")},{rng("B")},"B",{rng("M")},"Budget hold")', t["Bhold"]),
    ]
    first_tot = k
    for label, formula, value in tot_rows:
        out.append(f'<row r="{k}">{c_str(f"I{k}", label, "tlabel")}'
                   f'{c_num(f"J{k}", round(value, 4), "tusd", formula)}'
                   f'{c_num(f"L{k}", round(value * KWD_PER_USD, 4), "tkwd", f"J{k}*{rate}")}</row>')
        k += 1
    out.append(f'<row r="{k}">{c_str(f"I{k}", "Total", "tlabel")}'
               f'{c_num(f"J{k}", round(t["all"], 4), "tusd", f"SUM(J{first_tot}:J{k - 1})")}'
               f'{c_num(f"L{k}", round(t["all"] * KWD_PER_USD, 4), "tkwd", f"J{k}*{rate}")}</row>')
    total_row = k
    k += 1
    share = 'SUMIFS(%s,%s,"Listing")/J%d' % (rng("J"), rng("N"), total_row)
    out.append(f'<row r="{k}">{c_str(f"I{k}", "Share backed by a listing", "tlabel")}'
               f'{c_num(f"J{k}", round(t["listed"] / t["all"], 6), "pct", share)}</row>')

    cols = "".join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                   for i, (_, w, _) in enumerate(COLUMNS, 1))
    hyper = ""
    if links:
        hyper = "<hyperlinks>" + "".join(f'<hyperlink ref="{ref}" r:id="rIdL{i}"/>'
                                         for i, (ref, _) in enumerate(links, 1)) + "</hyperlinks>"
    sheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>
<dimension ref="A1:{LASTCOL}{k}"/>
<sheetViews><sheetView workbookViewId="0" tabSelected="1"><pane xSplit="4" ySplit="1" topLeftCell="E2" activePane="bottomRight" state="frozen"/><selection pane="topRight" activeCell="E1" sqref="E1"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/><selection pane="bottomRight" activeCell="E2" sqref="E2"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>{cols}</cols>
<sheetData>{"".join(out)}</sheetData>
<autoFilter ref="A1:{LASTCOL}{last}"/>
{hyper}
<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>
<pageSetup paperSize="1" orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>"""
    rels = ""
    if links:
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(f'<Relationship Id="rIdL{i}" Type="http://schemas.openxmlformats.org/officeDocument/'
                          f'2006/relationships/hyperlink" Target={quoteattr(url)} TargetMode="External"/>'
                          for i, (_, url) in enumerate(links, 1))
                + "</Relationships>")
    return sheet, rels, last


README_ROWS = [
    ("title", "PR-01  Initial purchase request: test supplies and long-lead hardware"),
    ("text", "AIAA Design/Build/Fly 2026–27  ·  Badr Obtel  ·  "
             "Doc OBTEL-DBF-27-PR-001  ·  Rev A  ·  9 Oct 2026"),
    ("text", "Generated by procurement/make_pr.py from procurement/pr01_items.csv. Edit the CSV, then run "
             "procurement/build.sh; this workbook and the PDF are rebuilt together."),
    ("rate", ("USD → KWD", KWD_PER_USD, "KWD per USD. " + RATE_SOURCE + ". Replace with the CBK rate "
              "if purchasing requires it; every KWD cell follows this one.")),
    ("rate", ("GBP → USD", USD_PER["GBP"], "USD per GBP. " + RATE_SOURCE + ".")),
    ("blank", ""),
    ("head", "How to read the Items sheet"),
    ("text", "Status, Buy now: the specification is fixed; order now."),
    ("text", "Status, Budget hold: the category and quantity are known, but the exact part follows the 13 Oct "
             "sizing gate (analysis Scripts 3–5). Reserve the budget now; part numbers follow on 14 Oct."),
    ("text", "Price basis, Listing: the vendor's listed price, checked on 9 Oct 2026 (URL in column P). "
             "Column R says whether it was read on the vendor page or taken from search results for that "
             "page, which can lag the live page. A reference, not a quote."),
    ("text", "Price basis, Estimate: a planning figure that has not been verified. Get a quote."),
    ("text", "Prices exclude shipping, duties and VAT unless the vendor column says otherwise."),
    ("blank", ""),
    ("head", "Purchasing constraints from the contest rules (2026–27 draft)"),
    ("text", "Receivers: ExpressLRS 2.4 GHz with PWM outputs (team decision, 8 Oct 2026). Do not substitute "
             "CRSF-only receivers: they need a flight controller, and flight controllers are banned "
             "(§3.2.1, §4.2.1). Buy FCC firmware versions: the radio must use a legal US frequency (§3.2.1)."),
    ("text", "Batteries: every pack (propulsion, receiver, sensor) must be commercial off-the-shelf, unaltered, "
             "with the manufacturer's label stating chemistry, capacity, voltage and C-rating (§3.2.3, §3.1.1). "
             "Propulsion packs ≤ 100 Wh each and ≤ 100 Wh in total (§3.2.3.2). Keep the original packaging: "
             "tech inspection checks it (§4.2.3)."),
    ("text", "Charging sacks: commercial, unaltered, manufacturer-labelled (§3.2.3)."),
    ("text", "Fuses: blade type in a separate harness; rating ≤ the pack's maximum continuous current, "
             "capped at 100 A (§3.2.3.1, §3.2.3.2)."),
    ("text", "Arming plug: wire the same gauge as the pack leads or heavier (§3.2.2)."),
    ("text", "ESCs: the BEC must be disabled, and a separate receiver battery is mandatory (§3.2.3, FAQ A.3)."),
    ("text", "No cameras, GPS, autopilots or flight controllers anywhere on the airplane (§3.2.1, §4.2.1)."),
    ("text", "Hatches: positive mechanical latches; magnets are not acceptable (§4.2.1)."),
    ("blank", ""),
    ("head", "Not in this request (budget items tracked separately)"),
    ("text", f"Fly-off registration fee: US${FLYOFF_FEE:,} per team (§2.6)."),
    ("text", f"AIAA student membership: US${AIAA_DUES} per member per year (aiaa.org dues page, checked "
             "9 Oct 2026); required for every team member (§1.1, §2.1)."),
    ("text", "AMA membership for the pilot (§1.2): price to be confirmed with AMA."),
    ("text", "Travel to Tucson and aircraft freight: separate travel request. Contingency: set by the team lead."),
]


def readme_sheet():
    out = []
    for k, (kind, payload) in enumerate(README_ROWS, 1):
        if kind == "blank":
            continue
        if kind == "rate":
            label, value, note = payload
            out.append(f'<row r="{k}">{c_str(f"A{k}", label, "mono")}{c_num(f"B{k}", value, "rate")}'
                       f'{c_str(f"C{k}", note, "note")}</row>')
            continue
        style = {"title": "title", "head": "tlabel", "text": "text"}[kind]
        ht = ' ht="22" customHeight="1"' if kind == "title" else ""
        out.append(f'<row r="{k}"{ht}>{c_str(f"A{k}", payload, style)}</row>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<dimension ref="A1:C{len(README_ROWS)}"/>
<sheetViews><sheetView workbookViewId="0" showGridLines="0"/></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols><col min="1" max="1" width="14" customWidth="1"/><col min="2" max="2" width="12" customWidth="1"/><col min="3" max="3" width="110" customWidth="1"/></cols>
<sheetData>{"".join(out)}</sheetData>
<pageMargins left="0.5" right="0.5" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>
</worksheet>"""


def write_xlsx(rows, t):
    # The Read me sheet holds the rates; Items formulas point at them.
    sheet1, sheet1_rels, last = items_sheet(rows, t)
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns_off = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts = {
        "[Content_Types].xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        "_rels/.rels": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{ns_rel}">
<Relationship Id="rId1" Type="{ns_off}/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="{ns_off}/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        "docProps/core.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>PR-01 Initial purchase request</dc:title><dc:creator>DBF team</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-09T00:00:00Z</dcterms:created>
</cp:coreProperties>""",
        "docProps/app.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>make_pr.py</Application></Properties>""",
        "xl/workbook.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{ns_off}">
<bookViews><workbookView activeTab="0"/></bookViews>
<sheets><sheet name="Items" sheetId="1" r:id="rId1"/><sheet name="Read me" sheetId="2" r:id="rId2"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Items!$A$1:${LASTCOL}${last}</definedName><definedName name="_xlnm.Print_Titles" localSheetId="0">Items!$1:$1</definedName></definedNames>
<calcPr calcId="191029" fullCalcOnLoad="1"/>
</workbook>""",
        "xl/_rels/workbook.xml.rels": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{ns_rel}">
<Relationship Id="rId1" Type="{ns_off}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="{ns_off}/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="{ns_off}/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/styles.xml": STYLES_XML,
        "xl/worksheets/sheet1.xml": sheet1,
        "xl/worksheets/sheet2.xml": readme_sheet(),
    }
    if sheet1_rels:
        parts["xl/worksheets/_rels/sheet1.xml.rels"] = sheet1_rels
    with zipfile.ZipFile(XLSX, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():   # fixed timestamps: identical rebuilds
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 9, 0, 0, 0)), data.encode("utf-8"),
                       compress_type=zipfile.ZIP_DEFLATED)


def main():
    rows = load()
    t = totals(rows)
    write_tex(rows, t)
    write_xlsx(rows, t)
    budget = write_budget(rows)
    print(f"ok    {len(rows)} lines  | Tier A US${money(t['A'])} | Tier B buy US${money(t['Bbuy'])}"
          f" | holds US${money(t['Bhold'])} | total US${money(t['all'])}"
          f" = KWD {t['all'] * KWD_PER_USD:,.3f} | listed share {100 * t['listed'] / t['all']:.0f}%")
    print("      proposal Table 02: " + " | ".join(f"{k} {v:,}" for k, v in budget.items())
          + f" | sum {sum(budget.values()):,}")
    print(f"      -> build/pr01_*.tex, {XLSX.name}, ../proposal/data/{PROPOSAL_BUDGET.name}")


if __name__ == "__main__":
    main()
