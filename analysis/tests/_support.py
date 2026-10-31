# Copyright © 2026 Badr Obtel. All rights reserved.
"""Shared helpers for the analysis tests (TOOLING).

- A function that still raises NotImplementedError is SKIPPED with the reason
  "not written yet: <name>" ("optional, not written yet" for optional ones),
  so FAIL always means a wrong answer.
- assertClose compares floats with a relative tolerance taken from the
  derivation: 1e-9 for closed forms, i.e. floating-point round-off only.
"""
import math
import sys
import unittest
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parents[1]
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

# Passed explicitly to every function: the pinned values were derived with it,
# so they do not move if constants.toml ever changes.
G = 9.80665
REL = 1e-9


class Case(unittest.TestCase):
    def call(self, fn, *args, optional=False, **kwargs):
        """Call fn; skip (not fail) the test while its body is still a stub."""
        try:
            return fn(*args, **kwargs)
        except NotImplementedError:
            tag = "optional, not written yet" if optional else "not written yet"
            self.skipTest(f"{tag}: {fn.__name__}")

    def assertClose(self, actual, expected, rel=REL, abs_tol=1e-12, msg=None):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            self.fail(msg or f"expected a number, got {actual!r}")
        if not math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_tol):
            self.fail(msg or f"got {actual!r}, expected {expected!r} "
                             f"(relative tolerance {rel:g})")

    def assertWhole(self, actual, expected, msg=None):
        """An integer count (laps, inches); 9 and 9.0 both pass."""
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) \
                or not float(actual).is_integer() or actual != expected:
            self.fail(msg or f"got {actual!r}, expected the whole number {expected}")
