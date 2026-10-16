# Aerodynamics evidence (section and wing maximum lift)

Built 15 Oct 2026 for evidence gap E03 (CLmax). It covers the measured data behind `analysis/clmax_study.py`, `wing_clmax_validation.py`, `wing_clmax.py` and `clmax_impact.py`.

## Reproduce
```bash
python analysis/data/aero/fetch_aero.py                 # sources.toml -> raw/aero/ (gitignored), sources.lock
PYTHONIOENCODING=utf-8 python analysis/clmax_study.py   # 2-D: measured, XFoil check, candidates (~9 min first run, then cached)
PYTHONIOENCODING=utf-8 python analysis/wing_clmax_validation.py   # 3-D method against NACA TN 663
PYTHONIOENCODING=utf-8 python analysis/wing_clmax.py     # 3-D: our planforms (needs the two above)
PYTHONIOENCODING=utf-8 python analysis/clmax_impact.py   # what it does to the Script 6 optimum
```
XFoil and AVL live in `analysis/tools/` (see its README for sources and hashes).

## Files
| File | What |
|---|---|
| `sources.toml`, `sources.lock` | Registry of every source (URL, publisher, nature) and the SHA-256 of what was read |
| `fetch_aero.py` | Downloader; reuses `prop/fetch_prop.py`; also reads coordinate files (Selig or Lednicer) |
| `lsat.py` | Reader for the UIUC LSAT tabulated polars (Vols 1-3, 5, 6): runs, Cl_max, flap settings, increments |
| `coords.py` | Coordinate reader (both UIUC layouts), thickness, Selig writer for XFoil/AVL |
| `naca_tn663.toml` | Measured wing CLmax with partial-span plain flaps (NACA TN 663), read from its figures |

## Sources and what each supplies
- **UIUC LSATs Vols 1-3, 5:** wind-tunnel Cl_max of SD7037 (four models), SD7062, Clark Y, E387, FX 63-137 and others, Re 0.6-4.6 x 10^5, clean and with a leading-edge trip.
- **Williamson (UIUC MS thesis 2012; LSATs Vol 6):** plain flaps on W1011, W1015 (cf/c 0.20, 0.30) and AG40d-02r (0.25), 0-65 deg, Re 1-5 x 10^5. Stated uncertainty: lift 1.5 %, angle 0.08 deg (thesis Sec. 3.7).
- **NACA TN 663 (House 1938):** AR 6 rectangular and 5:1 tapered Clark Y wings, 20 % plain flaps at 60 deg over 0-100 % span. Measured CLmax; used only to validate the 3-D method.
- **UIUC coordinate database:** section geometry for XFoil and AVL.

## Limits
- All section data are 2-D, in a low-turbulence tunnel, on carefully finished models. A built wing is rougher. The trip runs show SD7062 loses 24-27 % of its Cl_max with a rough leading edge, Clark Y 14-17 %, and SD7037 nothing.
- SD7037 was tested only to Re 3 x 10^5; SD7034 and MH 114 were never tested in these volumes.
- No measured flapped SD7037 exists. Its flap increment comes from the AG40d-02r (8 %, cambered, 25 % flap), the closest tested section.
- The NACA CLmax values are read from figures (+/- 0.02). The 3-D validation pairs a Clark Y wing with a W1011 flap increment, at Re 6.2 x 10^5 against section data at 4 x 10^5.
- No source here covers a fuselage, a propeller slipstream or gaps in the flap hinge. A flight test (stall speed at known weight) is the final check.
