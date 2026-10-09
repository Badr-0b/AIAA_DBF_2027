# Procurement

University purchasing is slow, so the team requests early and in one batch. Each request is built from one CSV, so its PDF and its spreadsheet can never disagree.

| File | Purpose |
|---|---|
| `pr01_items.csv` | **The source.** One row per line item. Edit this file only |
| `PR-01_initial_request.pdf` | House-style request for the team and the faculty advisor |
| `PR-01_initial_request.xlsx` | The same lines for the purchasing office: vendor links, need-by dates, USD and KWD columns |
| `make_pr.py` | Generator. Uses the Python standard library only |
| `build.sh` | Runs `make_pr.py`, then builds the PDF |

## Update after quotes arrive
1. Edit `pr01_items.csv` (UTF-8). Put the quoted price in `ref_price`, set `basis` to `listing`, and fill `ref_vendor`, `ref_url`, `checked` and `checked_via` (`page` or `search`).
2. When a budget hold gets its part number, change `status` from `hold` to `buy` and update `spec`.
3. Run `./build.sh` from Git Bash. It prints the totals and rebuilds both outputs.

If Excel opens the CSV with garbled symbols, import it as UTF-8 (Data > From Text/CSV). The purchasing office only needs the .xlsx.

## Columns
| Column | Meaning |
|---|---|
| `tier` | `A` local purchase this week; `B` formal university request |
| `status` | `buy` (specification fixed) or `hold` (budget reserved; part follows the sizing gate) |
| `basis` | `listing` (the vendor's listed price on `checked`) or `estimate` (unverified planning figure) |
| `checked_via` | For listings: `page` (read on the vendor page) or `search` (from search results for that page, which can lag) |
| `ref_price`, `ref_cur` | Price as listed, in its own currency (USD or GBP). Rates live at the top of `make_pr.py` |
| `supports` | The test card, requirement (SR) or rule section the line serves |

The rules constraints that purchasing must respect are listed in Section 4.0 of the PDF and on the spreadsheet's "Read me" sheet.
