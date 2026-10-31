"""S9 aircraft geometry schema ("s9-geom/1") and validator.

One JSON document describes one aircraft. Every other stream reads it through
geometry.io.load(), which calls validate() and raises on errors.

Frame (the AVL and CFD body frame; see memos/09_geometry.md):
    x  aft, from the datum origin (default: the most forward point of the fuselage)
    y  starboard (right wing tip at +y)
    z  up
Units: metres, kilograms, degrees (every angle key ends in "_deg").

The schema is published as JSON Schema (draft 2020-12) in SCHEMA. validate()
implements the subset of JSON Schema used here (type, required, properties,
items, enum, minimum, exclusiveMinimum, maximum, minItems, maxItems) plus
semantic checks a JSON Schema cannot express (section order, control spans,
airfoil references, mirrored bodies, mass totals).

Extensibility: any key starting with "x_" is accepted anywhere and ignored by
the S9 tools; free-form data goes under the top-level "extensions" object.
Unknown keys that do not start with "x_" give a WARNING, not an error, so a
newer document still loads in an older tool.
"""
from __future__ import annotations

import copy
import json

SCHEMA_ID = "s9-geom/1"

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
NUM = {"type": "number"}
POS = {"type": "number", "exclusiveMinimum": 0}
NONNEG = {"type": "number", "minimum": 0}
XYZ = {"type": "array", "items": NUM, "minItems": 3, "maxItems": 3,
       "description": "point [x, y, z] in m, body frame"}
STR = {"type": "string"}
FRAC = {"type": "number", "minimum": 0, "maximum": 1}


def obj(props, required=(), desc=""):
    d = {"type": "object", "properties": props, "required": list(required)}
    if desc:
        d["description"] = desc
    return d


SECTION = obj({
    "y": {**NUM, "description": "station along the surface's local span axis, m (0 = surface origin)"},
    "x_le": {**NUM, "description": "leading-edge x offset from the surface origin, m (local frame)"},
    "z_le": {**NUM, "description": "leading-edge offset normal to the span axis, m (local frame; polyhedral)"},
    "chord": POS,
    "twist_deg": {**NUM, "description": "section incidence, nose up +, rotation about the leading edge"},
    "airfoil": {**STR, "description": "name in the top-level 'airfoils' library, 'NACAxxxx', or a path to a .dat file"},
    "nspan": {"type": "integer", "minimum": 1, "description": "AVL spanwise vortices to the next section (optional)"},
}, ["y", "x_le", "chord"], "one airfoil section of a lifting surface")

CONTROL = obj({
    "name": {**STR, "description": "AVL control variable name (flap, aileron, elevator, rudder, ...)"},
    "function": {"enum": ["flap", "aileron", "flaperon", "elevator", "rudder", "ruddervator_pitch",
                          "ruddervator_yaw", "elevon_pitch", "elevon_roll", "spoiler", "other"]},
    "type": {"enum": ["plain", "split", "slotted", "double_slotted", "fowler", "all_moving"]},
    "y_start": {**NUM, "description": "local span station where the control starts, m (inboard end)"},
    "y_end": {**NUM, "description": "local span station where the control ends, m"},
    "chord_fraction": {**FRAC, "description": "control chord / local chord (hinge at 1 - cf)"},
    "gain": {**NUM, "description": "AVL gain, deg of surface per unit control (default 1)"},
    "sign_dup": {"enum": [1, -1, 1.0, -1.0], "description": "AVL SgnDup for the mirrored half: +1 symmetric (flap, elevator), -1 antisymmetric (aileron)"},
    "deflection_range_deg": {"type": "array", "items": NUM, "minItems": 2, "maxItems": 2},
    "fowler_extension": {**NONNEG, "description": "chord extension at full deflection / local chord (Fowler only)"},
    "gap": {**NONNEG, "description": "slot gap / chord (slotted only, metadata)"},
}, ["name", "function", "type", "y_start", "y_end", "chord_fraction"])

TIP_DEVICE = obj({
    "type": {"enum": ["none", "winglet", "tip_plate"]},
    "height": {**POS, "description": "winglet length along its span, or plate height above + below, m"},
    "fraction_below": {**FRAC, "description": "tip plate only: share of the height below the wing chord line"},
    "cant_deg": {**NUM, "description": "winglet cant from vertical, deg (0 = vertical, outward +)"},
    "root_chord": POS, "tip_chord": POS,
    "sweep_le_deg": NUM, "toe_deg": NUM,
    "airfoil": STR,
}, ["type"])

SURFACE = obj({
    "name": STR,
    "role": {"enum": ["wing", "htail", "vtail", "vee_tail", "canard", "winglet", "tip_plate", "pylon", "strut", "other"]},
    "component": {**STR, "description": "CFD patch / drawing group name (wing, htail, vtail, nacelle, ...)"},
    "symmetric": {"type": "boolean", "description": "mirror about y = 0 (AVL YDUPLICATE 0)"},
    "origin": XYZ,
    "dihedral_deg": {**NUM, "description": "rotation of the local span axis about +x: 0 horizontal, 90 vertical fin (up), "
                                           "V-tail = its dihedral, inverted V negative"},
    "incidence_deg": {**NUM, "description": "added to every section twist (AVL ANGLE)"},
    "sections": {"type": "array", "items": SECTION, "minItems": 2},
    "controls": {"type": "array", "items": CONTROL},
    "tip_device": TIP_DEVICE,
    "avl": obj({"nchord": {"type": "integer", "minimum": 1}, "nspan": {"type": "integer", "minimum": 1},
                "cspace": NUM, "sspace": NUM, "component": {"type": "integer", "minimum": 1},
                "nowake": {"type": "boolean"}, "claf": {"type": "boolean"}}),
}, ["name", "role", "symmetric", "origin", "sections"])

STATION = obj({
    "x": {**NUM, "description": "station x from the body origin, m"},
    "width": NONNEG, "height": NONNEG,
    "z": {**NUM, "description": "section centre z offset from the body origin, m"},
    "exponent": {"description": "superellipse exponent n (2 ellipse, >2 boxier) or [n_top, n_bottom]",
                 "type": ["number", "array"], "items": POS},
}, ["x", "width", "height"])

BODY = obj({
    "name": STR,
    "role": {"enum": ["fuselage", "pod", "boom", "nacelle", "fairing", "canopy", "other"]},
    "component": STR,
    "symmetric": {"type": "boolean", "description": "mirror a body at y != 0 to make a pair (twin booms, wing nacelles)"},
    "origin": XYZ,
    "stations": {"type": "array", "items": STATION, "minItems": 2},
    "avl": {"enum": ["body", "plates", "none"], "description": "how to_avl models it (default: body for fuselage, none otherwise)"},
}, ["name", "role", "origin", "stations"])

PROP = obj({
    "name": STR,
    "position": {**XYZ, "description": "hub centre on the disc plane, m"},
    "diameter": POS, "pitch": POS,
    "type": {"enum": ["tractor", "pusher"]},
    "symmetric": {"type": "boolean", "description": "mirror to y < 0 (a pair)"},
    "rotation": {"enum": ["cw", "ccw"], "description": "seen from behind"},
    "blades": {"type": "integer", "minimum": 1},
    "spinner_diameter": NONNEG,
    "motor": STR, "label": STR,
}, ["name", "position", "diameter", "type"])

WHEEL = obj({
    "name": STR, "position": {**XYZ, "description": "axle centre, m"},
    "diameter": POS, "width": POS,
    "symmetric": {"type": "boolean"},
    "strut_top": {**XYZ, "description": "strut attachment point, m (drawing only)"},
    "steerable": {"type": "boolean"},
}, ["name", "position", "diameter", "width"])

GEAR = obj({
    "type": {"enum": ["tricycle", "taildragger", "bicycle", "quadricycle", "skid", "none"]},
    "retractable": {"type": "boolean"},
    "faired": {"type": "boolean"},
    "wheels": {"type": "array", "items": WHEEL},
}, ["type"])

SLOT = obj({
    "name": STR,
    "kind": {"enum": ["sensor", "container", "simulator", "sensor_in_container", "ballast", "battery", "other"]},
    "dims": {"type": "array", "items": POS, "minItems": 3, "maxItems": 3, "description": "[length x, width y, height z], m"},
    "center": XYZ,
    "mass": NONNEG,
    "missions": {"type": "array", "items": STR},
}, ["name", "kind", "dims", "center"])

PAYLOAD = obj({
    "bay": obj({"x_start": NUM, "x_end": NUM, "width": POS, "height": POS, "z_center": NUM,
                "door": {"enum": ["none", "hinged", "sliding", "slot"]}},
               ["x_start", "x_end", "width", "height", "z_center"]),
    "slots": {"type": "array", "items": SLOT},
})

DR = obj({
    "reel": obj({"center": XYZ, "diameter": POS, "width": POS, "mass": NONNEG,
                 "axis": {"enum": ["x", "y", "z"]}}, ["center", "diameter", "width"]),
    "tow_exit": {**XYZ, "description": "point where the line leaves the skin, m (deploy length is measured from here)"},
    "line_length": POS,
    "sensor_stowed_center": XYZ,
    "sensor_dims": {"type": "array", "items": POS, "minItems": 3, "maxItems": 3},
}, ["reel", "tow_exit"])

MASS = obj({
    "name": STR, "mass": NONNEG, "xyz": XYZ,
    "inertia": {"type": "array", "items": NUM, "minItems": 3, "maxItems": 6,
                "description": "[Ixx, Iyy, Izz(, Ixy, Ixz, Iyz)] about the item's own CG, kg m^2"},
    "group": STR, "grade": {"enum": ["verified", "reseller", "estimate", "computed"]},
    "source": STR, "missions": {"type": "array", "items": STR},
}, ["name", "mass", "xyz"])

AIRFOIL = obj({
    "file": {**STR, "description": "coordinate file (Selig or Lednicer), relative to the JSON file or to src/geometry/airfoils"},
    "naca": {**STR, "description": "4-digit NACA designation, generated analytically"},
    "source": STR,
})

META = obj({
    "id": STR, "variant": STR, "revision": STR, "date": STR, "author": STR,
    "status": {"enum": ["reference", "draft", "candidate", "finalist", "frozen"]},
    "notes": {"type": "array", "items": STR},
    "sources": {"type": "object"},
}, ["id", "revision"])

REFERENCE = obj({
    "S_ref": POS, "b_ref": POS, "c_ref": POS,
    "xyz_ref": {**XYZ, "description": "moment reference point (default: the CG from 'masses', else the MAC quarter chord)"},
}, desc="optional overrides; props.wetted() computes them from the main wing when absent")

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_ID,
    "title": "DBF 2027 parametric aircraft (S9 geometry toolkit)",
    "description": "Body frame x aft, y starboard, z up; metres, kilograms, degrees. Keys starting with x_ are extensions.",
    "type": "object",
    "required": ["schema", "meta", "surfaces"],
    "properties": {
        "schema": {"enum": [SCHEMA_ID]},
        "meta": META,
        "reference": REFERENCE,
        "airfoils": {"type": "object", "additionalProperties": AIRFOIL},
        "surfaces": {"type": "array", "items": SURFACE, "minItems": 1},
        "bodies": {"type": "array", "items": BODY},
        "propellers": {"type": "array", "items": PROP},
        "gear": GEAR,
        "payload": PAYLOAD,
        "dr": DR,
        "masses": {"type": "array", "items": MASS},
        "extensions": {"type": "object"},
    },
}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
class GeometryError(ValueError):
    """Raised by io.load() when validate() finds errors."""

    def __init__(self, errors, warnings=()):
        self.errors, self.warnings = list(errors), list(warnings)
        super().__init__("geometry invalid:\n  " + "\n  ".join(self.errors))


_PY = {"number": (int, float), "integer": (int,), "string": (str,), "boolean": (bool,),
       "object": (dict,), "array": (list, tuple)}


def _is(v, t):
    if t in ("number", "integer") and isinstance(v, bool):
        return False
    if t == "integer" and isinstance(v, float) and v.is_integer():
        return True
    return isinstance(v, _PY[t])


def _check(v, s, path, err, warn):
    t = s.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_is(v, x) for x in ts):
            err.append(f"{path}: expected {'/'.join(ts)}, got {type(v).__name__} {v!r:.40}")
            return
    if "enum" in s and v not in s["enum"]:
        err.append(f"{path}: {v!r} not one of {s['enum']}")
    if _is(v, "number"):
        if "minimum" in s and v < s["minimum"]:
            err.append(f"{path}: {v} < minimum {s['minimum']}")
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            err.append(f"{path}: {v} must be > {s['exclusiveMinimum']}")
        if "maximum" in s and v > s["maximum"]:
            err.append(f"{path}: {v} > maximum {s['maximum']}")
    if isinstance(v, dict):
        props = s.get("properties", {})
        for k in s.get("required", []):
            if k not in v:
                err.append(f"{path}: missing required key '{k}'")
        addl = s.get("additionalProperties")
        for k, val in v.items():
            if k in props:
                _check(val, props[k], f"{path}.{k}", err, warn)
            elif isinstance(addl, dict):
                _check(val, addl, f"{path}.{k}", err, warn)
            elif props and not str(k).startswith("x_") and s.get("type") == "object" and path != "$.extensions":
                warn.append(f"{path}: unknown key '{k}' (prefix extensions with x_)")
    if isinstance(v, (list, tuple)):
        if "minItems" in s and len(v) < s["minItems"]:
            err.append(f"{path}: needs at least {s['minItems']} items, has {len(v)}")
        if "maxItems" in s and len(v) > s["maxItems"]:
            err.append(f"{path}: at most {s['maxItems']} items, has {len(v)}")
        if "items" in s:
            for i, it in enumerate(v):
                _check(it, s["items"], f"{path}[{i}]", err, warn)


def _semantic(g, err, warn):
    import math
    afl = g.get("airfoils", {})
    names = set()
    for i, s in enumerate(g.get("surfaces", [])):
        p = f"$.surfaces[{i}] ({s.get('name')})"
        if s.get("name") in names:
            err.append(f"{p}: duplicate surface name")
        names.add(s.get("name"))
        secs = s.get("sections", [])
        ys = [c.get("y", 0.0) for c in secs]
        if any(b < a for a, b in zip(ys, ys[1:])):
            err.append(f"{p}: section y must be non-decreasing (root to tip)")
        for j, c in enumerate(secs):
            a = c.get("airfoil")
            if a and a not in afl and not str(a).upper().startswith("NACA") and not str(a).lower().endswith(".dat"):
                err.append(f"{p}.sections[{j}]: airfoil '{a}' not in the airfoils library")
        if s.get("symmetric") and secs and s.get("origin", [0, 0, 0])[1] < -1e-9:
            warn.append(f"{p}: symmetric surface with origin y < 0; the mirror image overlaps")
        if secs:
            y0, y1 = ys[0], ys[-1]
            for k, c in enumerate(s.get("controls", [])):
                if not (y0 - 1e-9 <= c.get("y_start", 0) < c.get("y_end", 0) <= y1 + 1e-9):
                    err.append(f"{p}.controls[{k}] ({c.get('name')}): span [{c.get('y_start')}, {c.get('y_end')}] "
                               f"outside the surface [{y0}, {y1}] or empty")
                if c.get("type") == "fowler" and "fowler_extension" not in c:
                    warn.append(f"{p}.controls[{k}]: Fowler flap without fowler_extension")
        if abs(s.get("dihedral_deg", 0.0)) > 180:
            err.append(f"{p}: dihedral_deg outside [-180, 180]")
    for i, b in enumerate(g.get("bodies", [])):
        p = f"$.bodies[{i}] ({b.get('name')})"
        xs = [st.get("x", 0.0) for st in b.get("stations", [])]
        if any(bb <= aa for aa, bb in zip(xs, xs[1:])):
            err.append(f"{p}: station x must increase strictly")
        if b.get("symmetric") and abs(b.get("origin", [0, 0, 0])[1]) < 1e-9:
            warn.append(f"{p}: symmetric body on the centreline would be duplicated onto itself; ignored")
    m = g.get("masses", [])
    if m:
        tot = sum(x.get("mass", 0.0) for x in m)
        if tot <= 0:
            warn.append("$.masses: total mass is zero")
        elif tot > 24.948:
            warn.append(f"$.masses: total {tot:.2f} kg is not below the 24.948 kg (55 lb) TOGW limit (rules 3.1)")
    ws = [s for s in g.get("surfaces", []) if s.get("role") == "wing"]
    if not ws:
        warn.append("$.surfaces: no surface with role 'wing'; reference values must be given in 'reference'")
    for s in ws:
        if s.get("symmetric") and s.get("sections"):
            o, sec = s.get("origin", [0, 0, 0]), s["sections"][-1]
            gam = math.radians(s.get("dihedral_deg", 0.0))
            ytip = o[1] + sec["y"] * math.cos(gam) - sec.get("z_le", 0.0) * math.sin(gam)
            if 2 * ytip > 1.8288 + 1e-9:
                warn.append(f"wing '{s['name']}': projected span {2 * ytip:.4f} m exceeds 1.8288 m (6 ft), "
                            "before tip devices (rules 3.1; S1 owns the compliance check)")


def validate(geom):
    """Return (errors, warnings), two lists of strings. errors == [] means valid."""
    err, warn = [], []
    if not isinstance(geom, dict):
        return ["$: geometry must be a JSON object"], []
    _check(geom, SCHEMA, "$", err, warn)
    if not err:
        _semantic(geom, err, warn)
    return err, warn


def check(geom):
    """validate() and raise GeometryError on any error; returns the warnings."""
    err, warn = validate(geom)
    if err:
        raise GeometryError(err, warn)
    return warn


def schema_json(indent=1):
    """The JSON Schema document as text (written to early/S9_schema.json)."""
    return json.dumps(SCHEMA, indent=indent)


def template():
    """A minimal valid document to copy from."""
    return copy.deepcopy({
        "schema": SCHEMA_ID,
        "meta": {"id": "NEW", "revision": "A", "status": "draft", "notes": []},
        "airfoils": {"SD7037": {"file": "sd7037.dat"}},
        "surfaces": [{"name": "wing", "role": "wing", "component": "wing", "symmetric": True,
                      "origin": [0.3, 0.0, 0.1], "dihedral_deg": 0.0, "incidence_deg": 0.0,
                      "sections": [{"y": 0.0, "x_le": 0.0, "z_le": 0.0, "chord": 0.5, "airfoil": "SD7037"},
                                   {"y": 0.9, "x_le": 0.05, "z_le": 0.0, "chord": 0.35, "airfoil": "SD7037"}]}],
    })
