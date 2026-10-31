# Copyright © 2026 Badr Obtel. All rights reserved.
"""ParaView images of a finished external-aero case (half model, mirrored for display).

    pvbatch --force-offscreen-rendering cfd/tools/render_aero.py <run dir> <image dir>

Reads the latest time of the decomposed case, system/caseParameters (UMag) and
constant/geometry/reference (span, MAC, MAC leading edge, body box). Monochrome per the team
design system (design-system/README.md): Bone -> Ink scales, Geist Mono labels.
Images: surface Cp (top, bottom, iso), skin friction (top: shows transition),
y+ (top), speed on the MAC section and the centreline, total-pressure loss behind
the aircraft (wake and tip vortices), streamlines at the tip, and the layer mesh at the MAC.
Every camera is placed explicitly (no ResetCamera: it re-centres on the whole 23 m domain
for slices). Labels avoid "|": VTK then switches to its MathText renderer and drops the font.
"""
import math
import os
import re
import sys

from paraview.simple import (Calculator, CellDatatoPointData, ColorBy, CreateView, GetColorTransferFunction,
                             GetOpacityTransferFunction, GetScalarBar, Hide, MergeBlocks, OpenFOAMReader,
                             Reflect, Render, SaveScreenshot, Show, Slice, StreamTracer, Text, Tube,
                             _DisableFirstRenderCameraReset)

CASE = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "..", "design-system", "fonts", "GeistMono", "GeistMono-Regular.ttf")
RES = [1800, 1000]

hexrgb = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]  # noqa: E731
INK, GRAPHITE, STEEL, FOG, MIST, BONE = map(hexrgb, ("#0B0C0E", "#2B2E33", "#5B616B", "#A9AEB6", "#E4E6E9", "#F3F2EE"))
WHITE = [1.0, 1.0, 1.0]


def value(path, key):
    m = re.search(rf"^\s*{key}\s+([^;]+);", open(path).read(), re.M)
    return m.group(1).strip()


def vec(s):
    return [float(x) for x in s.strip("()").split()]


U = float(value(f"{CASE}/system/caseParameters", "UMag"))
REF = f"{CASE}/constant/geometry/reference"
SPAN, MAC, MACY = (float(value(REF, k)) for k in ("span", "refLength", "macY"))
XLE, _, ZW = vec(value(REF, "macLE"))
BMIN, BMAX = vec(value(REF, "bodyMin")), vec(value(REF, "bodyMax"))
ALPHA = value(f"{CASE}/system/alphaState", "alphaDeg")
Q = 0.5 * U * U
LABEL = f"alpha {float(ALPHA):+.1f} deg   U {U:g} m/s   Re(MAC) {U * MAC / float(value(f'{CASE}/system/caseParameters', 'nuAir')):,.0f}"

foam = os.path.join(CASE, "case.foam")
open(foam, "a").close()
_DisableFirstRenderCameraReset()


def reader(regions):
    r = OpenFOAMReader(FileName=foam)
    r.CaseType = "Decomposed Case"
    r.UpdatePipelineInformation()
    avail = list(r.GetProperty("MeshRegions").Available)
    r.MeshRegions = [a for a in avail if regions(a)]
    r.CellArrays = ["p", "U", "k", "nut", "gammaInt", "yPlus", "wallShearStress"]
    t = max(r.TimestepValues) if r.TimestepValues else 0
    r.UpdatePipeline(t)
    return r, t, avail


PATCHES = ("wing", "fuselage", "vtail", "nacelle")
walls, T, AVAIL = reader(lambda a: a.startswith("patch/") and a.split("/")[-1] in PATCHES)
print("time", T, "regions", AVAIL)
vol, _, _ = reader(lambda a: a == "internalMesh")

surf = Reflect(Input=CellDatatoPointData(Input=MergeBlocks(Input=walls)), Plane="Y", Center=0.0, CopyInput=1)
surf = Calculator(Input=surf, ResultArrayName="Cp", Function=f"p/{Q}")
surf = Calculator(Input=surf, ResultArrayName="Cf", Function=f"mag(wallShearStress)/{Q}")
volp = CellDatatoPointData(Input=vol)
volp = Calculator(Input=volp, ResultArrayName="Umag", Function=f"mag(U)/{U}")
volp = Calculator(Input=volp, ResultArrayName="Cp0", Function=f"(p+0.5*mag(U)^2)/{Q}")

view = CreateView("RenderView")
view.ViewSize = RES
view.OrientationAxesVisibility = 0
try:
    view.UseColorPaletteForBackground = 0
except AttributeError:
    pass
view.Background = WHITE


def lut(name, lo, hi, invert=False):
    """Monochrome scale; invert puts Ink at the low end (suction, low speed, loss)."""
    stops = [BONE, MIST, FOG, STEEL, GRAPHITE, INK]
    if invert:
        stops = stops[::-1]
    f = GetColorTransferFunction(name)
    pts = []
    for i, c in enumerate(stops):
        pts += [lo + (hi - lo) * i / (len(stops) - 1)] + c
    f.RGBPoints = pts
    f.ColorSpace = "Lab"
    f.AutomaticRescaleRangeMode = "Never"
    f.RescaleTransferFunction(lo, hi)
    GetOpacityTransferFunction(name).RescaleTransferFunction(lo, hi)
    return f


def bar(f, title):
    b = GetScalarBar(f, view)
    b.Title = title
    b.ComponentTitle = ""
    for k in ("TitleFontFamily", "LabelFontFamily"):
        setattr(b, k, "File")
    b.TitleFontFile = FONT
    b.LabelFontFile = FONT
    b.TitleColor = INK
    b.LabelColor = INK
    b.TitleFontSize = 16
    b.LabelFontSize = 14
    b.Orientation = "Horizontal"
    b.WindowLocation = "Lower Right Corner"
    b.ScalarBarLength = 0.33
    b.RangeLabelFormat = "%-#.3g"
    b.Visibility = 1
    return b


def caption(title):
    t = Text(Text=f"{title}\n{LABEL}")
    d = Show(t, view)
    d.FontFamily = "File"
    d.FontFile = FONT
    d.FontSize = 15
    d.Color = INK
    d.Justification = "Left"
    d.WindowLocation = "Upper Left Corner"
    return t


def camera(pos, focal, up, scale=None, angle=30):
    """Explicit camera: parallel projection with half-height `scale` (m), else perspective."""
    view.CameraPosition = pos
    view.CameraFocalPoint = focal
    view.CameraViewUp = up
    view.CameraParallelProjection = 1 if scale else 0
    if scale:
        view.CameraParallelScale = scale
    else:
        view.CameraViewAngle = angle


def shot(name, shown):
    Render(view)
    SaveScreenshot(os.path.join(OUT, name), view, ImageResolution=RES, TransparentBackground=0)
    for s in shown:
        Hide(s, view)
    for b in list(view.Representations):
        if hasattr(b, "Title") and hasattr(b, "Visibility"):
            b.Visibility = 0
    print("wrote", name)


cx = 0.5 * (BMIN[0] + BMAX[0])
cz = 0.5 * (BMIN[2] + BMAX[2])
L = BMAX[0] - BMIN[0]
far = 10 * SPAN
NOSE_UP = [-1, 0, 0]   # planform views: nose at the top, flow downwards


def surface_map(name, field, lo, hi, title, symbol, invert, pos, up, scale):
    d = Show(surf, view)
    ColorBy(d, ("POINTS", field))
    f = lut(field, lo, hi, invert)
    d.LookupTable = f
    bar(f, symbol)
    t = caption(title)
    camera(pos, [cx, 0, cz], up, scale)
    shot(name, [surf, t])


surface_map("cp_top.png", "Cp", -1.2, 1.0, "Pressure coefficient (upper surfaces)", "Cp", True,
            [cx, 0, cz + far], NOSE_UP, 0.33 * SPAN)
surface_map("cp_bottom.png", "Cp", -1.2, 1.0, "Pressure coefficient (lower surfaces)", "Cp", True,
            [cx, 0, cz - far], NOSE_UP, 0.33 * SPAN)
surface_map("cf_top.png", "Cf", 0.0, 0.010, "Skin friction coefficient (upper surfaces; laminar low, turbulent high)",
            "Cf", False, [cx, 0, cz + far], NOSE_UP, 0.33 * SPAN)
surface_map("yplus_top.png", "yPlus", 0.0, 2.0, "First-cell y+ (upper surfaces; target 1 or less)", "y+", False,
            [cx, 0, cz + far], NOSE_UP, 0.33 * SPAN)

# Iso view, perspective, from ahead, left and above
d = Show(surf, view)
ColorBy(d, ("POINTS", "Cp"))
f = lut("Cp", -1.2, 1.0, True)
d.LookupTable = f
bar(f, "Cp")
t = caption("Pressure coefficient")
dx, dy, dz = (1.35 * SPAN * c / math.dist((0, 0, 0), (-1.4, 0.9, 0.7)) for c in (-1.4, 0.9, 0.7))
camera([cx + dx, dy, cz + dz], [cx, 0, cz], [0, 0, 1], angle=24)
shot("cp_iso.png", [surf, t])


def section(name, origin, normal, field, lo, hi, title, symbol, invert, pos, up, scale, focal, edges=False, mirror=False):
    s = Slice(Input=volp)
    s.SliceType = "Plane"
    s.SliceType.Origin = origin
    s.SliceType.Normal = normal
    try:
        s.Triangulatetheslice = 0
    except AttributeError:
        pass
    shown_src = Reflect(Input=s, Plane="Y", Center=0.0, CopyInput=1) if mirror else s
    d = Show(shown_src, view)
    shown = [shown_src]
    if edges:
        d.SetRepresentationType("Surface With Edges")
        ColorBy(d, None)
        d.AmbientColor = WHITE
        d.DiffuseColor = WHITE
        d.EdgeColor = GRAPHITE
    else:
        ColorBy(d, ("POINTS", field))
        f = lut(field, lo, hi, invert)
        d.LookupTable = f
        bar(f, symbol)
    t = caption(title)
    shown.append(t)
    camera(pos, focal, up, scale)
    shot(name, shown)


mac_mid = [XLE + 0.5 * MAC, MACY, ZW]
section("u_mac_section.png", [0, MACY, 0], [0, 1, 0], "Umag", 0.0, 1.3,
        "Speed / freestream speed on the MAC section (wing interior blank)", "V / V_inf", True,
        [mac_mid[0], MACY - far, ZW], [0, 0, 1], 0.5 * MAC, mac_mid)
section("u_centreline.png", [0, 1e-4, 0], [0, 1, 0], "Umag", 0.0, 1.3,
        "Speed / freestream speed on the centreline (fuselage, nacelle duct)", "V / V_inf", True,
        [cx, -far, cz], [0, 0, 1], 0.36 * L, [cx, 0, cz])
le_zoom = [XLE + 0.12 * MAC, MACY, ZW]
section("mesh_mac_section.png", [0, MACY, 0], [0, 1, 0], None, 0, 1,
        "Mesh on the MAC section at the leading edge (prism layers)", None, False,
        [le_zoom[0], MACY - far, ZW], [0, 0, 1], 0.10 * MAC, le_zoom, edges=True)
xw = BMAX[0] + 0.1 * SPAN
section("wake_cp0.png", [xw, 0, 0], [1, 0, 0], "Cp0", 0.6, 1.0,
        f"Total-pressure coefficient {xw - BMAX[0]:.3g} m behind the tail, looking forward (wake, tip vortices)",
        "Cp0", True, [xw + far, 0, cz], [0, 0, 1], 0.30 * SPAN, [xw, 0, cz], mirror=True)

# Streamlines from a spanwise rake under the outer wing, ahead of the leading edge: they roll up into the tip vortex
seed = StreamTracer(Input=volp, SeedType="Line")
seed.Vectors = ["POINTS", "U"]
seed.IntegrationDirection = "FORWARD"
seed.SeedType.Point1 = [XLE - 0.3 * MAC, 0.42 * SPAN, ZW - 0.012 * SPAN]
seed.SeedType.Point2 = [XLE - 0.3 * MAC, 0.505 * SPAN, ZW - 0.012 * SPAN]
seed.SeedType.Resolution = 20
seed.MaximumStreamlineLength = 0.8 * SPAN
tubes = Tube(Input=seed)
tubes.Radius = 0.001 * SPAN
ds = Show(tubes, view)
ColorBy(ds, ("POINTS", "Umag"))
f = lut("Umag", 0.6, 1.2, True)
ds.LookupTable = f
bar(f, "V / V_inf")
dw = Show(surf, view)
ColorBy(dw, None)
dw.DiffuseColor = FOG
t = caption("Streamlines past the wing tip (tip vortex)")
tip = [XLE + 0.5 * MAC, 0.5 * SPAN, ZW]   # from behind, outboard and above, looking forward at the tip
camera([tip[0] + 0.75 * SPAN, tip[1] + 0.40 * SPAN, ZW + 0.30 * SPAN], [tip[0] + 0.15 * SPAN, tip[1] - 0.05 * SPAN, ZW],
       [0, 0, 1], angle=30)
shot("streamlines_tip.png", [tubes, surf, t])
print("done")
