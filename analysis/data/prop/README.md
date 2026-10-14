# Propulsion data (Script 3b)

Evidence behind the propulsion model (`analysis/s3b_propulsion.py`). Same rules
as the rest of `analysis/data/`: primary sources only, every value carries its
source and a verbatim quote, and one command re-checks everything.

## Reproduce
```bash
python analysis/data/prop/fetch_prop.py    # download every source in sources.toml into raw/prop/ (gitignored, ~100 MB)
python analysis/data/prop/verify_prop.py   # check every quote and value; writes components.csv and stands.csv
python analysis/prop_validation.py         # model vs measured data (run before using any result)
python analysis/prop_trade.py              # the trade (about 6 min)
```
`sources.lock` records the SHA-256 of every file read (14 Oct 2026). Some
servers refuse Python's HTTP client, so `fetch_prop.py` uses curl; APC serves
its files only to a session that opened the referring page, which the fetcher
does first.

## What is here
| File | Holds | Nature |
|---|---|---|
| `sources.toml` | Registry: APC performance archive, RPM-limit sheet and price list; UIUC Propeller Database (Vols 1-4) and the Vol. 4 paper; T-Motor AT product pages; SunnySky X7015; Thunder Power and MaxAmps pack pages | |
| `propdata.py` | Readers: APC PER3 tables straight from the hashed archive, UIUC runs from its zip, T-Motor spec and test tables from the cached pages | tooling |
| `components.toml` | Pack specs (capacity, cells, C rating or current limit, mass), the SunnySky motor, and the method statements the model relies on | SPEC, STATEMENT |
| `stands.toml` | Measured propulsion data from AIAA top-3 reports: WashU 2022 and MIT 2022 stands, UW 2023 static thrust at RPM, ERAU 2023 M2 flight energy, fuse tests, UW 2023 resting voltage | MEASURED |
| `verify_prop.py` | The checker (reuses `verify.py`'s normaliser and page finder) | tooling |

## What each source is
- **APC tables are COMPUTED** ("a specialized computational method that is based on Vortex theory", APC performance-data page). They cover every APC prop at every RPM.
- **UIUC data are MEASURED** (wind tunnel, Glauert and fairing corrections, calibration drift ≤ 1 %): 17 APC Thin Electric props of 12-21 in (Vol. 4, props bought 2019-21, tested to ~4,500-7,000 RPM) and 3 older ones (Vol. 1).
- **T-Motor test tables are MEASURED by the manufacturer** (voltage, current, power, RPM, torque, thrust, per Kv winding and prop): 23 windings, 1,282 rows. The AT5220-B and AT5230-B pages repeat the -A tables and are not registered twice. The AT5330-A page has no table.
- **Pack data are manufacturer SPEC.** Thunder Power labels its masses "*estimate only*". Pack internal resistance is published by none of them; the model's value is an ESTIMATE calibrated on WashU 2022 (`inputs/propulsion.toml`).

## Known limits (stated in the reports)
- UIUC Vol. 4 says its coefficients use the propellers' "true diameter", but no geometry is published for Vol. 4, so the basis is treated as nominal. Efficiency is independent of the reference diameter, so the efficiency comparison is unaffected.
- The fuse in the rules' Figure 5 links to a generic, unbranded 100 A MAXI fuse with no datasheet. Littelfuse's MAXI datasheet (the documented reference for the form factor) blocks scripted downloads; the AIAA team tests in `stands.toml` are the evidence used.
- Innov8tive Designs (Cobra motors, MIT 2022) refuses scripted access, so the MIT stand is not used to check a motor model; it reports no RPM, voltage or current anyway.
- WashU 2022 names an "X7025-30cc-270" motor. SunnySky's 30cc frame is the X7015 and its 270 kV winding is the 7015KV270, which is assumed (`stands.toml`); that point tunes nothing.
