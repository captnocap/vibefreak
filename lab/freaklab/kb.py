"""Reading the knowledge base in lab/kb/: look sounds up by measurement, and say settings the way the panel does."""
import json
import os
import re

from . import analyze

KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb")
_cache = {}


def _load(name):
    if name not in _cache:
        path = os.path.join(KB, name)
        _cache[name] = json.load(open(path)) if os.path.exists(path) else None
    return _cache[name]


def osc_files():
    d = os.path.join(KB, "osc")
    return sorted(f for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def osc_tables():
    return [_load(os.path.join("osc", f)) for f in osc_files()]


def osc_points(engine=None):
    """Every measured oscillator setting as (table, point)."""
    want = re.sub(r"[ ._-]", "", engine).lower() if engine else None
    for table in osc_tables():
        if want and not re.sub(r"[ ._-]", "", table["engine"]).lower().startswith(want):
            continue
        for p in table["points"]:
            if not p.get("silent"):
                yield table, p


def clock(percent):
    """Knob pointer as a clock position: 7 o'clock hard left, 12 straight up, 5 hard right."""
    hours = 7 + percent / 100 * 10
    hours = hours - 12 if hours >= 13 else hours
    h = int(hours)
    m = int(round((hours - h) * 60 / 15) * 15)
    if m == 60:
        h, m = h + 1, 0
    h = h - 12 if h > 12 else h
    return f"{h}:{m:02d}" if m else f"{h} o'clock"


def knob_shown(knob, percent):
    """What the screen reads with a knob at `percent`, from the recorded calibration (nearest recorded position)."""
    panel = _load("panel.json") or {}
    if knob not in panel:
        return None
    pts = panel[knob]["points"]
    return min(pts, key=lambda p: abs(p[0] - percent))[1]


def knob_text(knob, percent):
    shown = knob_shown(knob, percent)
    label = (_load("panel.json") or {}).get(knob, {}).get("label", knob)
    if knob == "filter_amount":
        return f"Filter Amount: {percent:+.0f} (knob at {clock(50 + percent / 2)}; 12 o'clock is zero)"
    tail = f", screen reads about {shown}" if shown else ""
    return f"{label}: {percent:.0f}% of the knob ({clock(percent)}){tail}"


def osc_text(table, point):
    """An oscillator setting in the words and numbers the instrument's screen uses."""
    parts = []
    for knob in ("wave", "timbre", "shape"):
        shown = table["shown"][knob].get(str(point[knob]))
        parts.append(f"{table['labels'][knob]} {shown if shown is not None else str(point[knob]) + '%'}")
    return f"{table['engine']}: " + ", ".join(parts)


_OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}


def find(engine=None, words=(), where=(), sort=None, limit=12):
    """Measured settings that carry every word and pass every 'feature>number' test."""
    tests = []
    for expr in where:
        m = re.fullmatch(r"\s*(\w+)\s*(>=|<=|>|<)\s*(-?[\d.]+)\s*", expr)
        if not m:
            raise ValueError(f"cannot read condition '{expr}' (use e.g. centroid_harm>4)")
        tests.append((m.group(1), _OPS[m.group(2)], float(m.group(3))))
    hits = []
    for table, p in osc_points(engine):
        if any(not any(w.lower() in have.lower() for have in p.get("words", [])) for w in words):
            continue
        if any(p.get(k) is None or not op(p[k], v) for k, op, v in tests):
            continue
        hits.append((table, p))
    if sort:
        key, _, direction = sort.partition(":")
        hits = [h for h in hits if h[1].get(key) is not None]
        hits.sort(key=lambda h: h[1][key], reverse=(direction != "asc"))
    return hits[:limit] if limit else hits


def match(features, engine=None, limit=8):
    """Measured settings whose spectrum shape is closest to `features` (pitch-independent)."""
    scored = [(analyze.profile_distance(features, p), table, p) for table, p in osc_points(engine)]
    scored.sort(key=lambda s: s[0])
    return scored[:limit]


# ---------------------------------------------------------------------------
# GUIDE.md: the knowledge base boiled down to something short enough to read
# ---------------------------------------------------------------------------

TREND_FEATURES = [
    ("centroid_harm", "brightness centre (harmonic number)", 1),
    ("harmonic_share", "share of energy on the note's harmonics", 2),
    ("fundamental_share", "share of energy in the fundamental", 2),
    ("odd_even_db", "odd vs even harmonics (dB)", 0),
    ("below_f0_share", "share of energy below the note", 2),
    ("am_depth", "loudness wobble while held", 2),
    ("level_db", "level (dB)", 0),
]

CORNERS = [
    ("darkest", "centroid_harm", False),
    ("brightest", "centroid_harm", True),
    ("purest (most energy in the fundamental)", "fundamental_share", True),
    ("most hollow (odd harmonics lead)", "odd_even_db", True),
    ("most even-harmonic (octave-like)", "odd_even_db", False),
    ("least pitched (noise or clangour)", "harmonic_share", False),
    ("most beating", "am_depth", True),
    ("most weight below the note", "below_f0_share", True),
]


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _fmt(v, digits):
    return "-" if v is None else f"{v:.{digits}f}"


def _engine_section(table):
    pts = [p for p in table["points"] if not p.get("silent")]
    silent = len(table["points"]) - len(pts)
    labels = table["labels"]
    lines = [f"## {table['engine']}", "",
             f"Knobs: Wave = **{labels['wave']}**, Timbre = **{labels['timbre']}**, Shape = **{labels['shape']}**. "
             f"{len(table['points'])} settings measured at C3 (130.8 Hz), oscillator output only."]
    if silent:
        lines.append(f"{silent} of them were silent in the emulator.")
    if not pts:
        lines += ["", "No sound came out of the emulator for this type, so nothing is known about it yet.", ""]
        return lines
    lines.append("")
    for knob in ("wave", "timbre", "shape"):
        shown = table["shown"][knob]
        texts = [shown.get(str(g)) for g in table["grid"]]
        numeric = all(t is not None and t.replace(".", "").replace("-", "").isdigit() for t in texts)
        if not numeric:
            lines.append(f"{labels[knob]} reads on screen, across the knob: " + " / ".join(str(t) for t in texts) + ".")
    lines += ["", "What each knob does, averaged over the other two (columns are the knob at "
              + ", ".join(str(g) for g in table["grid"]) + " percent):", ""]
    for knob in ("wave", "timbre", "shape"):
        lines.append(f"| {labels[knob]} | " + " | ".join(str(g) for g in table["grid"]) + " |")
        lines.append("|---|" + "---|" * len(table["grid"]))
        for key, title, digits in TREND_FEATURES:
            # odd/even is capped at +-40 dB before averaging: a clean digital square reads +80, which
            # would swamp everything it is averaged with
            cap = (lambda v: max(-40.0, min(40.0, v)) if v is not None else None) if key == "odd_even_db" else (lambda v: v)
            row = [_mean([cap(p.get(key)) for p in pts if p[knob] == g]) for g in table["grid"]]
            if all(v is None for v in row):
                continue
            spread = max(v for v in row if v is not None) - min(v for v in row if v is not None)
            if key != "centroid_harm" and spread < (1.5 if digits == 0 else 0.03):
                continue  # this knob does not move this measure
            lines.append(f"| {title} | " + " | ".join(_fmt(v, digits) for v in row) + " |")
        lines.append("")
    lines.append("Extremes found:")
    lines.append("")
    for title, key, highest in CORNERS:
        have = [p for p in pts if p.get(key) is not None]
        if not have:
            continue
        best = max(have, key=lambda p: p[key]) if highest else min(have, key=lambda p: p[key])
        if key in ("am_depth", "below_f0_share") and best[key] < 0.05:
            continue  # nothing in this type does it
        lines.append(f"- {title}: {osc_text(table, best).split(': ', 1)[1]} ({key} = {best[key]})")
    words = {}
    for p in pts:
        for w in p.get("words", []):
            words[w] = words.get(w, 0) + 1
    if words:
        common = sorted(words.items(), key=lambda kv: -kv[1])[:6]
        lines += ["", "How often each description applied: " + ", ".join(f"{w} {100 * n // len(pts)}%" for w, n in common) + "."]
    kbd = table.get("across_keyboard") or []
    if kbd:
        lines += ["", "Middle setting across the keyboard (note: brightness centre in Hz, share on harmonics): "
                  + "; ".join(f"{k['note']}: {_fmt(k.get('centroid_hz'), 0)} Hz, {_fmt(k.get('harmonic_share'), 2)}" for k in kbd) + "."]
    lines.append("")
    return lines


def build_guide():
    lines = open(os.path.join(KB, "GUIDE.head.md")).read().rstrip().split("\n") + [""]
    panel = _load("panel.json")
    if panel:
        lines += ["# Knob positions and what the screen reads", "",
                  "Percent of knob travel, then the text the instrument shows there.", ""]
        for knob, d in panel.items():
            lines.append(f"- **{d['label']}**: " + ", ".join(f"{p:.0f}% = {s}" for p, s in d["points"][::2]))
        lines.append("")
    env = _load("envelope.json")
    if env:
        lines += ["# Envelope, measured from the firmware's own control signal", "",
                  "Attack (knob percent: ms to reach 90 % / 99 % of full level): "
                  + ", ".join(f"{r['knob']}: {r.get('to_90pct_ms')} / {r.get('to_99pct_ms')}" for r in env["attack"]) + ".", "",
                  "Decay with Sustain at 0 (knob: ms down to 50 % / 10 %): "
                  + ", ".join(f"{r['knob']}: {r.get('down_to_50pct_ms')} / {r.get('down_to_10pct_ms')}" for r in env["decay"]) + ".", "",
                  "Release after a held note (same knob; ms down to 50 % / 10 %): "
                  + ", ".join(f"{r['knob']}: {r.get('down_to_50pct_ms')} / {r.get('down_to_10pct_ms')}" for r in env["release"]) + ".", "",
                  "Sustain (knob: held level as a fraction of the peak): "
                  + ", ".join(f"{r['knob']}: {r.get('held_level_vs_peak')}" for r in env["sustain"]) + ".", "",
                  "Filter Amount with Cutoff at 40 % (knob: how far the envelope pushes the cutoff, in octaves): "
                  + ", ".join(f"{r['knob']:+d}: {r['sweep_octaves']:+.2f}" for r in env["filter_amount"])
                  + ". The sweep stops at the ends of the cutoff range, which is why the largest settings read the same.", ""]
    filt = _load("filter.json")
    if filt:
        lines += ["# Filter (a model, see the caveats at the top)", ""]
        for mode in ("lp", "bp", "hp"):
            rows = [r for r in filt["rows"] if r["mode"] == mode]
            # only settings where the test tone (65 Hz sawtooth) has harmonics on both sides of the cutoff
            base = [r for r in rows if r["resonance"] == 0 and 300 <= r["model_cutoff_hz"] <= 12000]
            if mode == "bp":
                lines.append("**BP**. Cutoff knob: centre of the band: "
                             + ", ".join(f"{r['cutoff']}%: {r['peak_hz']:.0f} Hz" for r in base) + ".")
                continue
            lines.append(f"**{mode.upper()}**. Resonance knob: height of the peak at the cutoff, in dB (Cutoff at 50 %): "
                         + ", ".join(f"{r['resonance']}%: {r['peak_db']:+.1f}" for r in rows if r["cutoff"] == 50) + ".")
            lines.append("  Cutoff knob with Resonance at 0: point where the response is 3 dB down: "
                         + ", ".join(f"{r['cutoff']}%: {r.get('minus3db_hz', '-')} Hz" for r in base)
                         + ". With no resonance the model is very gentle, so this sits below the frequency on the screen.")
            slopes = [r.get("gain_1oct_db") for r in base if r.get("gain_1oct_db") is not None]
            slopes2 = [r.get("gain_2oct_db") for r in base if r.get("gain_2oct_db") is not None]
            if slopes and slopes2:
                lines.append(f"  Roll-off: about {sorted(slopes)[len(slopes) // 2]:.0f} dB one octave past the cutoff, "
                             f"{sorted(slopes2)[len(slopes2) // 2]:.0f} dB two octaves past.")
        kt = filt.get("key_tracking") or []
        if kt:
            lines += ["", "Cutoff while holding different notes, knob at 50 %: "
                      + ", ".join(f"note {k['note']}: {k['model_cutoff_hz']} Hz" for k in kt)
                      + ". If these are all the same, the cutoff does not follow the keyboard on its own."]
        lines.append("")
    lines += ["# Oscillator types", ""]
    for table in osc_tables():
        lines += _engine_section(table)
    with open(os.path.join(KB, "GUIDE.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return os.path.join(KB, "GUIDE.md")
