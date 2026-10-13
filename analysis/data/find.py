# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Search a cached source by page (TOOLING, for extraction work).

    python analysis/data/find.py <source_id> <first_page> <last_page> <regex> [--layout] [--context N]

Prints every matching line as  p<page>: <line>  so a value and its page can be
quoted exactly into a dataset row.
"""
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"


def main():
    sid, first, last, pattern = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    layout = "--layout" in sys.argv
    ctx = int(sys.argv[sys.argv.index("--context") + 1]) if "--context" in sys.argv else 0
    text = (RAW / f"{sid}{'.layout' if layout else ''}.txt").read_text(encoding="utf-8")
    rx = re.compile(pattern, re.I)
    for n, page in enumerate(text.split("\f")[first - 1:last], start=first):
        lines = page.splitlines()
        for i, line in enumerate(lines):
            if rx.search(line):
                for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
                    print(f"p{n}{':' if j == i else ' '} {lines[j].rstrip()}")
                if ctx:
                    print("     ---")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
