# Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.
"""One-line status of the analysis tests, for proposal/build.sh (TOOLING).

    python analysis/check.py          exit 0 only if every required test passes

Counts each test method once (its worst subtest): pass, fail (a wrong answer or
an error), not written (a required function still a stub) and optional not
written (lap_time_wind, round_rule; these never block).
"""
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent / "tests"
RANK = {"pass": 0, "optional": 1, "missing": 2, "fail": 3}


class Tally(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.status = {}
        self.problems = []

    def _note(self, test, state):
        tid = getattr(test, "test_case", test).id()   # a subtest counts for its parent test
        if RANK[state] >= RANK[self.status.get(tid, "pass")]:
            self.status[tid] = state

    def addSuccess(self, test):
        super().addSuccess(test)
        self._note(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._note(test, "fail")
        self.problems.append(test.id())

    def addError(self, test, err):
        super().addError(test, err)
        self._note(test, "fail")
        self.problems.append(test.id())

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._note(test, "optional" if reason.startswith("optional") else "missing")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._note(test, "fail")
            self.problems.append(subtest.id())


def main():
    sys.path.insert(0, str(TESTS))
    suite = unittest.defaultTestLoader.discover(str(TESTS), top_level_dir=str(TESTS))
    tally = Tally()
    suite.run(tally)
    count = {k: sum(1 for s in tally.status.values() if s == k) for k in RANK}
    line = (f"analysis tests: {count['pass']} pass, {count['fail']} fail, "
            f"{count['missing']} not written")
    if count["optional"]:
        line += f" (+{count['optional']} optional not written)"
    print(line)
    for name in dict.fromkeys(tally.problems):
        print(f"      FAIL {name}")
    return 0 if count["fail"] == 0 and count["missing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
