"""Sequence guard for dbfdoc documents.

Contest rules treat content that appears outside its section as missing.
LaTeX floats can drift past the next section heading, so after each build
this script reads the positions dbfdoc.cls writes to the .aux file and checks
that every figure/table lands after its own section heading and before the
next one, in two-column reading order (page, column, top to bottom).

    python check_order.py build/main.aux      -> exit 1 on any violation
"""
import re
import sys
from pathlib import Path

SP_PER_BP = 65781.76
MID_X = 306 * SP_PER_BP  # page centre on US Letter; column 2 starts right of it

label_re = re.compile(r"\\zref@newlabel\{(dbf-(?:sec|flt)-[^}]*)\}\{(.*)\}\s*$")
prop_re = re.compile(r"\\(posx|posy|abspage)\{(-?\d+)\}")


def reading_key(p):
    col = 1 if p["posx"] < MID_X else 2
    return (p["abspage"], col, -p["posy"])


def main(aux):
    secs, flts = {}, []
    for line in Path(aux).read_text(encoding="utf-8", errors="replace").splitlines():
        m = label_re.search(line)
        if not m:
            continue
        props = {k: int(v) for k, v in prop_re.findall(m.group(2))}
        if not {"posx", "posy", "abspage"} <= props.keys():
            continue
        name = m.group(1)
        if name.startswith("dbf-sec-"):
            secs[int(name.split("-")[2])] = props
        else:
            _, _, n, s, kind, num = name.split("-", 5)
            flts.append((int(n), int(s[1:]), f"{kind.capitalize()} {num}", props))

    bad = 0
    for n, s, what, p in sorted(flts):
        key = reading_key(p)
        if s in secs and key < reading_key(secs[s]):
            print(f"FAIL  {what} (section {s}.0) appears BEFORE its section heading "
                  f"(page {p['abspage']})")
            bad += 1
        if s + 1 in secs and key > reading_key(secs[s + 1]):
            print(f"FAIL  {what} (section {s}.0) appears AFTER the {s + 1}.0 heading "
                  f"(page {p['abspage']}): move its source earlier")
            bad += 1
    if not bad:
        print(f"PASS  sequence: all {len(flts)} floats sit inside their own sections")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build/main.aux"))
