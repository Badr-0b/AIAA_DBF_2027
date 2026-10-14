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
analysis/                   Mission math, studies and trades (Python). See analysis/README.md
decisions/                  Decision briefs for the team (DB-01). Run ./build.sh
SOURCES.md                  Every source behind any number, with links (generated: python analysis/data/sources_index.py)
reference/                  Context from past years
  past_proposals/           Top-3 scoring proposals from 2025-26 (RMIT, UC San Diego, Arkansas)
assets/branding/            Logos for reports/drawings
TODO.md                     Team task list
```

## Documents
Every written document uses the design system in [`design-system/`](design-system/), so each new document starts from `dbfdoc.cls`. Toolchain: MiKTeX (XeLaTeX), Python 3 with matplotlib, and Git Bash.

## Intellectual Property
Copyright © 2026 the members of the AUM AIAA DBF team. All rights reserved.

All original work in this repository, including designs, CAD, drawings, analysis, code, test data and documents, was created by the team members, who retain complete ownership of it. The American University of the Middle East (AUM) holds no ownership, license or other rights in this work unless the team grants them in writing. The university's name appears only to identify the team's academic affiliation, as the competition rules require, and does not transfer any rights.

No part of this repository may be copied, distributed, reproduced or used to create derivative works without written permission from the team.

**Exceptions.** Third-party material keeps its original owner and license:
- `rules/` and `assets/branding/AIAA_Logo_White.png`: AIAA
- `reference/past_proposals/`: the respective universities
- `design-system/fonts/`: SIL Open Font License (see each `OFL.txt`)

Under Section 6.1 of the 2026-27 rules, reports submitted to the competition become the property of AIAA, Textron Aviation and Raytheon. This notice does not override that rule.
