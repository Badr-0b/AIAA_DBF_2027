# Design System

The house style for **every** document this team produces: the proposal, the design report, memos and anything else written. The intent is a defense-prime technical dossier with Swiss restraint. *Expensive* here means precise, quiet and consistent. It never means decorated.

Do not restyle documents locally. If something is missing, add it here so every document gets it.

## Contents
| Path | What it is |
|---|---|
| `latex/dbfdoc.cls` | LaTeX class: page, type, color, headings, masthead, tables, captions, components, guards |
| `latex/dbf-identity.tex` | **The only place** for the team name, logo, university name and program line |
| `fonts/` | Geist, Geist Mono and IBM Plex Math (SIL Open Font License, so they may be redistributed and embedded) |
| `matplotlib/dbfplot.py` | Plot style: exact print sizes, house fonts, palette |
| `tools/build.sh` | Builds any dbfdoc document (XeLaTeX, two passes) |
| `tools/check_order.py` | Sequence guard: fails if any figure or table lands outside its own section |
| `examples/showcase.tex` | Every component on realistic pages (illustrative values) |

## Build
Requires MiKTeX (or TeX Live) with XeLaTeX, Python 3 with matplotlib, and Git Bash on Windows.
```bash
design-system/tools/build.sh path/to/main.tex [output.pdf]
```
Missing LaTeX packages install automatically during the build, with no dialog.

## The rules
**Page.** US Letter (8.5 × 11 in), always. Margins are 0.75 in. Two columns of 3.35 in with a 0.30 in gutter. Every figure and table is either **column width (3.35 in)** or **full width (7.00 in)**, never anything in between.

**Type.**

| Use | Style |
|---|---|
| Body | Geist 10 pt on a 17.25 pt baseline (contest "1.5 spacing") |
| Tables and captions | 9 pt |
| Footnotes | 8 pt |
| Section headings | Mono index (`3.0`) followed by the title in tracked capitals, with a hairline rule above |
| Labels, IDs and readouts | Geist Mono |

Tables use tabular figures automatically. Never use Arial, Calibri, Times or any default font.

**Color.** The palette is monochrome only:

| Name | Hex |
|---|---|
| Ink | `#0B0C0E` |
| Graphite | `#2B2E33` |
| Steel | `#5B616B` |
| Fog | `#A9AEB6` |
| Mist | `#E4E6E9` |
| Bone | `#F3F2EE` |

There is no signal color. Emphasis comes from weight, ink fills and the Bone tint. The selected option in a trade table is a Bone column under an **inverted ink header**. Never use university brand colors, gold or brass, or flag green or red.

**Tables (`dbftable`).** Hairline rules with no vertical lines, a Mist header in tracked capitals, and faint Mist row separators. Totals use `row{Z}={font=\dbftotalrow}`. Every table is explained in the text.

**Figures.** Use `dbfplot`: vector PDF built at final size, house fonts, mono tick labels, no titles inside plots (the caption is the title), and units on every axis. Only the design point or "ours" is emphasized. Diagrams use the same palette. CAD renders sit on a white background with consistent camera angles.

**Captions** state the takeaway rather than the topic. Write "Sensor weight moves the score most…", not "Sensitivity plot".

**Numbers** live in one data file per document and are referenced through macros. Never type a key number twice.

**Banned:**
- spreadsheet screenshots, default Excel or MATLAB charts, raster charts
- clip art, stock images, gradients, shadows, rounded "web" boxes, emoji
- fake classification markings
- the AIAA logo on our documents
- headings stranded at the bottom of a page, unexplained acronyms, unquantified adjectives

## Components
| Command | Purpose |
|---|---|
| `\dbfsetdoc{title}{type}{doc id}{rev}`, `\dbfsetdate{}` | Document control shown in the masthead and footer |
| `frontmatter` environment | Full-width page-1 block under the dark masthead |
| `dbfpanel` environment and `\dbfreadout{label}{value}{unit}` | "Design at a Glance" instrument panel |
| `dbftable` | House table (tabularray syntax) |
| `dbflongtable` | Same look, breaks across pages and repeats its header row. One-column pages only; put `\captionof{table}{...}\nopagebreak` above it |
| `\dbfplaceholder{w}{h}{label}` | Placeholder box at an exact grid size |
| `\dbfnote{...}` | Writer guidance. Removed by the `final` class option |
| `\dbftbd{label}` | A value not yet computed. Visible, and counted by the build |
| `\dbffill{N}` | N words of gray placeholder prose, used to prove page budgets |
| `\dbfselected{...}` | Emphasizes the winning value in a trade table |

## Floats and section order
Contest rules treat content outside its section as **missing**. LaTeX floats can drift, so the class records where every heading and caption lands, and `check_order.py` fails the build if any float leaves its section. If it fails, move the float's source earlier. In a document's last sections, use column-width floats with `[h]` placement.
