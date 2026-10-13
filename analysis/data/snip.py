# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""Propose verbatim quotes for a value on a page (TOOLING, for extraction work).

    python analysis/data/snip.py <source_id> <page> <value> [--before N] [--after N]

Prints every occurrence of <value> on the page, in each cached text mode
(.txt, .layout.txt, .raw.txt), as the whitespace-normalised text that
verify.py will search, with N characters either side. Copy the shortest
snippet that also names the quantity; if the text layer separates label and
value (multi-column tables), take a numeric run and confirm the row on the
rendered page (pdftoppm), saying so in the row's `where`.
"""
import sys

from verify import RAW, norm


def main():
    sid, page, value = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    before = int(sys.argv[sys.argv.index("--before") + 1]) if "--before" in sys.argv else 40
    after = int(sys.argv[sys.argv.index("--after") + 1]) if "--after" in sys.argv else 25
    v = norm(value)
    for suffix in (".txt", ".layout.txt", ".raw.txt"):
        f = RAW / f"{sid}{suffix}"
        if not f.exists():
            continue
        text = norm(f.read_text(encoding="utf-8").split("\f")[page - 1])
        i = text.find(v)
        while i >= 0:
            print(f"{suffix:12s}| {text[max(0, i - before):i + len(v) + after]}")
            i = text.find(v, i + 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
