"""Orchestrator figures for DB-02 (house style via dbfplot, read-only).
Run: PYTHONDONTWRITEBYTECODE=1 python report/figs_orch.py [name ...]
Writes report/figures/*.pdf only."""
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
REPO = W.parent
sys.path.insert(0, str(REPO / "design-system" / "matplotlib"))
import dbfplot as dp                                   # noqa: E402
import matplotlib.image as mpimg                       # noqa: E402
import numpy as np                                     # noqa: E402

FIG = W / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
dp.use()


def cfd_panel():
    a = mpimg.imread(W / "cfd/rq4_mock/results/alpha+04.0/images/cp_iso.png")
    b = mpimg.imread(W / "cfd/rq4_mock/results/alpha+12.0/images/u_mac_section.png")
    fig, axs = dp.figure("page", 2.25, ncols=2) if "ncols" in dp.figure.__code__.co_varnames else (None, None)
    if fig is None:
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, 2, figsize=(dp.PAGE, 2.25))
    for ax, img, crop, lab in ((axs[0], a, (250, 870, 0, 1800), "SURFACE PRESSURE  /  BODY 4°  /  26.5 M/S"),
                               (axs[1], b, (180, 800, 250, 1750), "SPEED ON MEAN CHORD  /  BODY 12°  /  STALLED")):
        y0, y1, x0, x1 = crop
        ax.imshow(img[y0:y1, x0:x1])
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True); s.set_linewidth(0.4); s.set_color(dp.FOG)
        ax.text(0.0, 1.03, lab, transform=ax.transAxes, fontfamily=dp.MONO, fontsize=5.8, color=dp.STEEL)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.90, bottom=0.02, wspace=0.03)
    dp.save(fig, FIG / "cfd_panel.pdf")


def _variant(key):
    d = json.loads((W / "out/variants/variants_geometry.json").read_text(encoding="utf-8"))
    return d[key]


def three_view(key, dark=False):
    """Vector 3-view (top, side, front) in house style from out/variants/variants_geometry.json."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle, Circle, FancyBboxPatch  # noqa: F401
    V = _variant(key)
    g, t, m = V["geometry"], V["tails"], V["mass"]
    ink = "#E4E6E9" if dark else dp.INK
    fog = dp.STEEL if dark else dp.FOG
    mist = "#2B2E33" if dark else dp.MIST
    bg = dp.INK if dark else "white"
    lw = 0.7
    W_, H_ = (6.7, 6.05) if dark else (dp.PAGE, 4.6)
    fig = plt.figure(figsize=(W_, H_), facecolor=bg)
    # axes: top view (left, tall), side view (top right), front view (bottom right)
    axT = fig.add_axes([0.02, 0.06, 0.46, 0.88])
    axS = fig.add_axes([0.52, 0.55, 0.46, 0.38])
    axF = fig.add_axes([0.52, 0.08, 0.46, 0.38])
    for ax in (axT, axS, axF):
        ax.set_facecolor(bg); ax.set_aspect("equal"); ax.axis("off")
    half = 0.91
    xr, cr, ct = g["x_le"], g["cr"], g["ct"]
    xt = xr + 0.25 * (cr - ct)
    L_f, wf, hf = g["fus_len"], g["fus_w"], g["fus_h"]
    x_end = t["x_ach"] + 0.6 * t["crh"]
    # ---- top view (x down the page, y across)
    def P(ax, pts, **kw):
        ax.add_patch(Polygon(pts, closed=True, fill=kw.pop("fill", False), **kw))
    wing = [(-half, -xt), (-0.0, -xr), (half, -xt), (half, -(xt + ct)), (0, -(xr + cr)), (-half, -(xt + ct))]
    P(axT, wing, ec=ink, lw=lw, fc=mist, fill=True, zorder=3)
    fs = g["flap_span"] * half
    for sgn in (-1, 1):
        y0, y1 = 0.17 * sgn, fs * sgn
        c0 = cr - (cr - ct) * abs(y0) / half; c1 = cr - (cr - ct) * abs(y1) / half
        x0 = xr + 0.25 * (cr - c0) + c0; x1 = xr + 0.25 * (cr - c1) + c1
        P(axT, [(y0, -x0), (y1, -x1), (y1, -(x1 - g["cf"] * c1)), (y0, -(x0 - g["cf"] * c0))], ec=fog, lw=0.4, zorder=4)
        ya0, ya1 = (fs + 0.02) * sgn, 0.97 * half * sgn
        c0 = cr - (cr - ct) * abs(ya0) / half; c1 = cr - (cr - ct) * abs(ya1) / half
        x0 = xr + 0.25 * (cr - c0) + c0; x1 = xr + 0.25 * (cr - c1) + c1
        P(axT, [(ya0, -x0), (ya1, -x1), (ya1, -(x1 - 0.25 * c1)), (ya0, -(x0 - 0.25 * c0))], ec=fog, lw=0.4, zorder=4)
    # fuselage
    fus = [(-wf / 2, -0.10), (wf / 2, -0.10), (wf / 2, -L_f), (0.06, -(x_end - 0.02)), (-0.06, -(x_end - 0.02)), (-wf / 2, -L_f)]
    P(axT, [(-wf / 2 * 0.8, -0.03), (wf / 2 * 0.8, -0.03), (wf / 2, -0.10), (-wf / 2, -0.10)], ec=ink, lw=lw, fc=bg, fill=True)
    P(axT, fus, ec=ink, lw=lw, fc=bg, fill=True)
    # h tail
    bh, crh, cth, xh = t["bh"], t["crh"], t["cth"], t["xh"]
    xht = xh + 0.25 * (crh - cth)
    P(axT, [(-bh / 2, -xht), (0, -xh), (bh / 2, -xht), (bh / 2, -(xht + cth)), (0, -(xh + crh)), (-bh / 2, -(xht + cth))],
      ec=ink, lw=lw, fc=mist, fill=True)
    # bay, CG, tow exit, prop
    xb = m["x_bay"]; cl, cw, ch = (0.298, 0.288, 0.288)
    axT.add_patch(Rectangle((-cw / 2, -(xb + cl / 2)), cw, cl, fill=False, ec=fog, lw=0.5, ls=(0, (3, 2)), zorder=5))
    axT.plot([-0.254, 0.254], [0.0, 0.0], color=ink, lw=1.2)
    xc = t["x_cg_design"]
    axT.add_patch(Circle((0, -xc), 0.028, fill=False, ec=ink, lw=0.6, zorder=6))
    axT.plot([-0.045, 0.045], [-xc, -xc], color=ink, lw=0.6, zorder=6); axT.plot([0, 0], [-xc - 0.045, -xc + 0.045], color=ink, lw=0.6, zorder=6)
    # dimension: span
    yd = 0.18
    axT.annotate("", xy=(-half, yd), xytext=(half, yd), arrowprops=dict(arrowstyle="<->", lw=0.4, color=fog))
    axT.text(0, yd + 0.03, f"SPAN {2*half:.3f} M", ha="center", va="bottom", fontfamily=dp.MONO, fontsize=5.6, color=fog)
    axT.text(half, -(x_end + 0.08), f"LENGTH {x_end:.2f} M  /  S {g['S']:.2f} M²  /  AR {g['AR']:.2f}", ha="right",
             va="top", fontfamily=dp.MONO, fontsize=5.6, color=fog)
    axT.set_xlim(-1.0, 1.0); axT.set_ylim(-(x_end + 0.2), 0.32)
    # ---- side view (x right, z up); ground at z = 0
    zb = t["axis_h"] if "axis_h" in t else 0.369
    zf0 = 0.369 - hf / 2                                   # fuselage bottom so the prop axis sits mid-height
    def S_(pts, **kw):
        P(axS, pts, **kw)
    S_([(0.03, zf0 + 0.04), (0.10, zf0), (L_f, zf0 + 0.05), (x_end - 0.02, zf0 + hf * 0.62), (x_end - 0.02, zf0 + hf * 0.75),
        (L_f, zf0 + hf), (0.10, zf0 + hf), (0.03, zf0 + hf - 0.04)], ec=ink, lw=lw, fc=bg, fill=True)
    zw = zf0 + hf
    S_([(xr, zw), (xr + cr, zw), (xr + cr, zw + 0.012), (xr + 0.1 * cr, zw + 0.05), (xr, zw + 0.03)], ec=ink, lw=lw, fc=mist, fill=True)
    zt = zf0 + hf * 0.68
    S_([(xh, zt), (xh + crh, zt), (xh + crh, zt + 0.012), (xh, zt + 0.012)], ec=ink, lw=lw, fc=mist, fill=True)
    bv, crv, ctv = t["bv"], t["crv"], t["ctv"]
    xv = t["x_ach"] - 0.25 * crv
    S_([(xv, zt), (xv + crv, zt), (xv + 0.35 * (crv - ctv) + ctv, zt + bv), (xv + 0.35 * (crv - ctv), zt + bv)],
       ec=ink, lw=lw, fc=mist, fill=True)
    axS.plot([0, 0], [0.369 - 0.254, 0.369 + 0.254], color=ink, lw=1.2)
    axS.plot([-0.1, x_end + 0.1], [0, 0], color=fog, lw=0.4)
    # gear: nose and mains
    for xg, r in ((0.16, 0.045), (xc + 0.16, 0.055)):
        axS.plot([xg, xg], [r, zf0], color=ink, lw=0.8)
        axS.add_patch(Circle((xg, r), r, fill=False, ec=ink, lw=0.6))
    axS.add_patch(Rectangle((xb - cl / 2, zf0 + 0.02), cl, ch, fill=False, ec=fog, lw=0.5, ls=(0, (3, 2))))
    axS.plot([xb, xb + 0.35], [zf0, zf0 - 0.25], color=fog, lw=0.5, ls=(0, (1, 2)))
    axS.text(xb + 0.37, zf0 - 0.27, "TOW LINE (M3)", fontfamily=dp.MONO, fontsize=5, color=fog, va="top")
    axS.set_xlim(-0.15, x_end + 0.15); axS.set_ylim(-0.05, 0.95)
    axS.text(-0.12, 0.92, "SIDE", fontfamily=dp.MONO, fontsize=5.6, color=fog)
    # ---- front view (y right, z up)
    dz = half * math.tan(math.radians(2.0))
    def F_(pts, **kw):
        P(axF, pts, **kw)
    F_([(-wf / 2, zf0), (wf / 2, zf0), (wf / 2, zf0 + hf), (-wf / 2, zf0 + hf)], ec=ink, lw=lw, fc=bg, fill=True)
    F_([(-half, zw + dz), (0, zw), (half, zw + dz), (half, zw + dz + 0.04), (0, zw + 0.05), (-half, zw + dz + 0.04)],
       ec=ink, lw=lw, fc=mist, fill=True)
    F_([(-bh / 2, zt), (bh / 2, zt), (bh / 2, zt + 0.012), (-bh / 2, zt + 0.012)], ec=ink, lw=lw, fc=mist, fill=True)
    F_([(-0.006, zt), (0.006, zt), (0.006, zt + bv), (-0.006, zt + bv)], ec=ink, lw=lw, fc=mist, fill=True)
    axF.add_patch(Circle((0, 0.369), 0.254, fill=False, ec=ink, lw=0.6))
    for yg, r in ((0, 0.045), (-0.30, 0.055), (0.30, 0.055)):
        axF.plot([yg, yg * 0.5], [r, zf0], color=ink, lw=0.8)
        axF.add_patch(Rectangle((yg - 0.012, 0), 0.024, 2 * r, fill=False, ec=ink, lw=0.6))
    axF.plot([-1.0, 1.0], [0, 0], color=fog, lw=0.4)
    axF.set_xlim(-1.0, 1.0); axF.set_ylim(-0.05, 0.95)
    axF.text(-0.98, 0.92, "FRONT", fontfamily=dp.MONO, fontsize=5.6, color=fog)
    axT.text(-0.98, 0.29, "TOP", fontfamily=dp.MONO, fontsize=5.6, color=fog)
    name = f"threeview_{key}{'_dark' if dark else ''}.pdf"
    fig.savefig(FIG / name, facecolor=bg)
    plt.close(fig)


def threeviews():
    for k in ("A", "B"):
        three_view(k, dark=False)
        three_view(k, dark=True)


def _label(s):
    lab = f"{s['s']:.1f} m², {dict(fowler='Fowler').get(s['flap'], s['flap'])}"
    return lab + (", twin" if s["prop"] == "twin" else "") + (f", 3–{s['m_hi']:g} kg" if s["m_hi"] != 6 else "")


def regret():
    """Candidates: A, B, every scenario leader not already shown, the DB-01 control (from the finalists' selection)."""
    F = json.loads((W / "out/integration/finalists.json").read_text(encoding="utf-8"))
    sel = F.pop("selection")
    scen = [("base", "Base case"), ("fowler_low", "Fowler underdelivers"), ("mass_up", "Airframe +15 %"),
            ("reliab_low", "Reliability lower"), ("combined", "Fowler low + heavy")]
    b = F["base"]
    cands = [(sel["A"], "A  " + _label(b[sel["A"]]), dp.INK, "o", True), (sel["B"], "B  " + _label(b[sel["B"]]), dp.INK, "s", False)]
    extra = []
    for sc, _ in scen:
        lead = max((k for k in F[sc] if k != "CTRL"), key=lambda k: F[sc][k]["p_mission_top"])
        if lead not in (sel["A"], sel["B"]) and lead not in extra:
            extra.append(lead)
    for k, (col, mk) in zip(extra[:3], ((dp.STEEL, "^"), (dp.FOG, "D"), (dp.FOG, "v"))):
        cands.append((k, _label(b[k]), col, mk, False))
    cands.append(("CTRL", "DB-01 control", dp.FOG, "x", False))
    fig, ax = dp.figure("page", 2.5)
    for j, (cid, lab, col, mk, fill) in enumerate(cands):
        xs, ys, lo, hi = [], [], [], []
        for i, (sc, _) in enumerate(scen):
            s = F[sc][cid]
            xs.append(i + (j - (len(cands) - 1) / 2) * 0.11); ys.append(s["p_mission_top"])
            lo.append(s["p_mission_top"] - s["p_mission_top_ci95"][0]); hi.append(s["p_mission_top_ci95"][1] - s["p_mission_top"])
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, ms=4 if cid in (sel["A"], sel["B"]) else 3.4, color=col,
                    mfc=col if fill else "white", mec=col, ecolor=col, elinewidth=0.6, capsize=0, lw=0, label=lab)
    ax.set_xticks(range(len(scen)), [s[1] for s in scen])
    ax.set_ylabel("P(highest mission total)")
    ys_all = [F[sc][c[0]]["p_mission_top_ci95"][k] for sc, _ in scen for c in cands for k in (0, 1)]
    ax.set_ylim(max(0.0, min(ys_all) - 0.02), max(ys_all) + 0.07)
    ax.legend(loc="upper right", frameon=False, ncol=3, fontsize=6.2)
    dp.save(fig, FIG / "regret.pdf")


def p1st():
    C = json.loads((W / "out/finalists/p1st_curves.json").read_text(encoding="utf-8"))
    fig, ax = dp.figure("col", 2.3)
    for cid, lab, col, ls in (("A", "Variant A", dp.INK, "-"), ("B", "Variant B", dp.STEEL, "--")):
        r = [a for a, _ in C[cid]]; p = [b for _, b in C[cid]]
        ax.plot(r, p, color=col, ls=ls, lw=1.1 if cid == "A" else 0.9, label=lab)
    ax.axvline(88, color=dp.FOG, lw=0.5, ls=":")
    ax.text(88.3, 0.02, "88", fontfamily=dp.MONO, fontsize=5.6, color=dp.STEEL)
    ax.set_xlabel("Our Total Report Score")
    ax.set_ylabel("P(1st overall)")
    ax.set_xlim(70, 96); ax.set_ylim(0, 0.5)
    ax.legend(loc="upper left", frameon=False)
    dp.save(fig, FIG / "p1st.pdf")


ALL = {"cfd_panel": cfd_panel, "threeviews": threeviews, "regret": regret, "p1st": p1st}

if __name__ == "__main__":
    names = sys.argv[1:] or list(ALL)
    for n in names:
        ALL[n]()
        print("ok", n)
