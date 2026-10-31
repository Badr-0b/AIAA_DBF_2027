# DB-02: aircraft variants for the 2027 fly-off

This folder holds everything produced by the DB-02 effort, which started on 27 Oct 2026:
- code, tests and results;
- CFD cases;
- the findings memos;
- the final PDF.

Nothing outside this folder is modified, and nothing here is committed until the team lead says so.

| Path | What it holds |
|---|---|
| `brief/00_BRIEF.md` | Shared brief: scope, rules facts, ground rules, the interface contract and the pre-registered selection rule |
| `memos/` | One findings memo per analysis stream |
| `src/`, `tests/`, `out/` | Stream code (Python), unittest suites, and results (`results.json`, CSV, figures) |
| `cfd/` | CFD case setups, harvested results and renders |
| `report/` | The DB-02 PDF source, style layer and build output |
| `sources/` | Sources added by this effort, kept for merging into `SOURCES.md` later |
| `ledger/` | Orchestrator's evidence ledger, finalists and storyline |
| `VARIANTS_SPEC.md` | Bare per-variant specification (rev B), every row tagged rules / datasheet / computed / estimate / assumed |
| `tools/rerun_chain.sh` | Re-runs the whole pipeline in order (trim geometry, screen, gates, finalists, layout, export, figures, numbers), about 6 min; then `bash report/build.sh DB-02_aircraft_variants.tex` |
| `out/_prefix_30oct/` | Revision A's results and PDF, kept for comparison |

To run this folder's tests:

```
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s DB-02_aircraft_variants/tests -p "test_v_*.py"
```
