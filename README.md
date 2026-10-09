# AIAA_DBF
This repository is for AUM's AIAA DBF team to keep track of any changes. Use this as the base of all operations.

## 2026-27 Theme: UAV with a towed sensor
Max wingspan of 6 ft. Three flight missions plus a ground mission (drop-testing the sensor shipping container).
The full rules are in [`rules/`](rules/).

## Key deadlines
| Event | Window |
|---|---|
| Entry + Proposal + Team Roster | 15 Oct 2026 08:00 ET to **31 Oct 2026 17:00 ET** |
| Proposal acceptance notice | by 20 Nov 2026 |
| Q&A submissions open | 1 Nov 2026 |
| Design Report + Config Drawing | 1 Feb 2027 08:00 ET to **19 Feb 2027 17:00 ET** |
| Fly-off (TIMPA, Tucson AZ) | 15 to 18 Apr 2027 |

## Repository layout
```
proposal/                   2026-27 proposal (LaTeX). Run ./build.sh. See proposal/README.md
testing/                    Test cards TC-01 to TC-04 (printable PDFs). Run ./build.sh
procurement/                Purchase requests: CSV source, PDF and .xlsx. Run ./build.sh
design-system/              House style for ALL team documents (class, fonts, plot style, tools)
rules/                      Official 2026-27 rules (draft) + proposal scoring rubric screenshot
reference/                  Context from past years
  past_proposals/           Top-3 scoring proposals from 2025-26 (RMIT, UC San Diego, Arkansas)
assets/branding/            Logos for reports/drawings
TODO.md                     Team task list
```

## Documents
Every written document uses the design system in [`design-system/`](design-system/), so each new document starts from `dbfdoc.cls`. Toolchain: MiKTeX (XeLaTeX), Python 3 with matplotlib, and Git Bash.
