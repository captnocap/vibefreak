"""Measurement runs that fill the knowledge base in lab/kb/.

Each run plays the emulated instrument through a grid of settings and stores
what was measured, labelled with what the firmware held and what its screen
showed. Nothing in the knowledge base is typed in by hand.

  osc     every oscillator type over a Wave x Timbre x Shape grid (raw oscillator output)
  filter  the filter model: cutoff, resonance and mode, as a response curve
  env     envelope timing straight from the firmware's VCA and cutoff control signals
"""
import json
import os
import tempfile
from multiprocessing import Pool

import numpy as np

from . import analyze, engines, params, patch
from .client import Lab, note_hz

KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb")
GRID = [0, 17, 33, 50, 67, 83, 100]
NOTE = 48  # C3, 130.81 Hz
HOLD_MS = 800


def _slim(f):
    """Keep what the knowledge base needs from one analysis, rounded so the files stay small."""
    if f.get("silent"):
        return {"silent": True}
    keep = ("level_db", "cents_off", "centroid_harm", "centroid_hz", "rolloff85_hz", "harmonic_share",
            "fundamental_share", "odd_even_db", "below_f0_share", "flatness", "am_depth", "am_rate_hz",
            "centroid_wobble", "centroid_drift", "sustain_ratio", "decay_half_ms", "words")
    out = {k: f[k] for k in keep if f.get(k) is not None}
    out["level_db"] = round(out["level_db"], 1)
    out["harmonics_db"] = [int(round(v)) for v in f["harmonics_db"][:16]]
    out["profile_db"] = [int(round(max(v, -99))) for v in f["profile_db"]]
    out["peaks"] = f["peaks"][:8]
    return out


def measure_point(lab, tmp, settings, note=NOTE, hold_ms=HOLD_MS):
    patch.apply(lab, settings)
    raw = os.path.join(tmp, "raw.wav")
    patch.play(lab, note, hold_ms, 0, raw_wav=raw, cv_every=0)
    lab.step(150)
    return analyze.analyze_file(raw, note_hz(note), hold_ms, oscillator_only=True)


def sweep_engine(name):
    eng = engines.lookup(name)
    tmp = tempfile.mkdtemp(prefix="freaksweep")
    with Lab() as lab:
        patch.apply(lab, patch.INIT)
        patch.apply(lab, {"engine": eng[0], "wave": 50, "timbre": 50, "shape": 50})
        # what the screen calls each grid position, one knob at a time
        shown = {"wave": {}, "timbre": {}, "shape": {}}
        for knob in shown:
            for v in GRID:
                patch.apply(lab, {knob: v})
                shown[knob][str(v)] = patch.osc_display(lab)[knob]["shown"]
            patch.apply(lab, {knob: 50})
        points = []
        for w in GRID:
            for t in GRID:
                for s in GRID:
                    f = measure_point(lab, tmp, {"wave": w, "timbre": t, "shape": s})
                    points.append({"wave": w, "timbre": t, "shape": s, **_slim(f)})
        # the same middle setting across the keyboard
        patch.apply(lab, {"wave": 50, "timbre": 50, "shape": 50})
        pitches = []
        for n in (24, 36, 48, 60, 72, 84):
            f = measure_point(lab, tmp, {}, note=n)
            pitches.append({"note": n, **{k: f.get(k) for k in ("f0_hz", "cents_off", "level_db", "centroid_harm",
                                                                 "centroid_hz", "harmonic_share")}})
    out = {
        "engine": eng[0], "labels": dict(zip(("wave", "timbre", "shape"), eng[3])), "faithful": eng[4],
        "note": NOTE, "note_hz": round(note_hz(NOTE), 2), "grid": GRID, "shown": shown,
        "points": points, "across_keyboard": pitches,
    }
    os.makedirs(os.path.join(KB, "osc"), exist_ok=True)
    path = os.path.join(KB, "osc", eng[0].replace(" ", "_").replace(".", "") + ".json")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    return eng[0], len(points), sum(1 for p in points if p.get("silent"))


def sweep_osc(names=None, jobs=12):
    names = names or [e[0] for e in engines.ENGINES if e[4]]
    with Pool(min(jobs, len(names))) as pool:
        for name, n, silent in pool.imap_unordered(sweep_engine, names):
            print(f"{name}: {n} points, {silent} silent", flush=True)


def _response(raw, post):
    """Filter gain in dB at each harmonic of a 65.4 Hz sawtooth: (frequencies, gains)."""
    f0 = note_hz(36)
    a, b = analyze.steady_window(raw, 150), analyze.steady_window(post, 150)
    fr, pa = analyze._spectrum(a)
    _, pb = analyze._spectrum(b)
    freqs, gains = [], []
    k = 1
    while f0 * k < 30000:
        _, x = analyze._peak_near(fr, pa, f0 * k, 0.01)
        _, y = analyze._peak_near(fr, pb, f0 * k, 0.01)
        if x > 1e-12:
            freqs.append(f0 * k)
            gains.append(10 * np.log10(max(y, 1e-15) / x))
        k += 1
    return np.array(freqs), np.array(gains)


def sweep_filter():
    """How the filter model responds, measured on a sawtooth an octave below C3."""
    tmp = tempfile.mkdtemp(prefix="freakfilt")
    rows = []
    with Lab() as lab:
        patch.apply(lab, patch.INIT)
        patch.apply(lab, {"engine": "BasicWaves", "wave": 50, "timbre": 0, "shape": 0})
        for mode in ("lp", "bp", "hp"):
            for res in (0, 25, 50, 75, 100):
                for cut in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
                    patch.apply(lab, {"filter": mode, "resonance": res, "cutoff": cut})
                    raw, post = os.path.join(tmp, "r.wav"), os.path.join(tmp, "p.wav")
                    patch.play(lab, 36, 700, 0, wav=post, raw_wav=raw, cv_every=0)
                    cv = lab.cv()
                    lab.step(120)
                    fr, g = _response(analyze.load(raw), analyze.load(post))
                    # take out the VCA's flat gain using the filter's pass band
                    ref = {"lp": np.median(g[:3]), "hp": np.median(g[-20:]), "bp": g.max()}[mode]
                    g = g - ref
                    ipk = int(np.argmax(g))
                    row = {"mode": mode, "resonance": res, "cutoff": cut,
                           "model_cutoff_hz": round(cv["model_cutoff_hz"], 1), "model_q": round(cv["model_q"], 2),
                           "peak_hz": round(float(fr[ipk]), 1), "peak_db": round(float(g[ipk]), 1)}
                    below = np.nonzero(g <= -3)[0]
                    if mode == "lp" and len(below):
                        row["minus3db_hz"] = round(float(fr[below[0]]), 1)
                    if mode == "hp" and len(below):
                        row["minus3db_hz"] = round(float(fr[below[-1]]), 1)
                    # slope: gain one and two octaves past the cutoff
                    fc = cv["model_cutoff_hz"]
                    for octv in (1, 2):
                        target = fc * 2 ** octv if mode == "lp" else fc / 2 ** octv
                        if fr[0] < target < fr[-1]:
                            row[f"gain_{octv}oct_db"] = round(float(np.interp(target, fr, g)), 1)
                    rows.append(row)
        # does the cutoff follow the keyboard?
        patch.apply(lab, {"filter": "lp", "resonance": 0, "cutoff": 50})
        tracking = []
        for n in (36, 48, 60, 72):
            lab.note_on(n)
            lab.step(200)
            tracking.append({"note": n, "cutoff_16b": lab.cv()["cutoff_16b"], "model_cutoff_hz": round(lab.cv()["model_cutoff_hz"], 1)})
            lab.note_off(n)
            lab.step(150)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    with open(os.path.join(KB, "filter.json"), "w") as fh:
        json.dump({"source": "BasicWaves sawtooth, note 36 (65.4 Hz)", "rows": rows, "key_tracking": tracking}, fh, indent=1)
    print(f"filter: {len(rows)} settings")


def _crossings(vca, step_ms):
    """Times (ms) at which a rising control signal passes 10, 90 and 99 % of its top."""
    top = vca.max()
    return {p: round(float(np.argmax(vca >= top * p / 100) * step_ms), 1) for p in (10, 90, 99)} if top > 0 else {}


def sweep_env():
    """Envelope and filter-envelope behaviour, read from the firmware's control outputs."""
    out = {"attack": [], "decay": [], "release": [], "sustain": [], "filter_amount": []}
    with Lab() as lab:
        patch.apply(lab, patch.INIT)
        step = None
        for a in (0, 10, 20, 30, 40, 50, 60, 70, 80):
            patch.apply(lab, {"attack": a, "sustain": 100, "decay": 0})
            lab.note_on(NOTE)
            r = lab.render(6000 if a >= 60 else 2500, cv_every=1)
            lab.note_off(NOTE)
            lab.step(400)
            step = r["cv"]["step_ms"]
            out["attack"].append({"knob": a, **{f"to_{k}pct_ms": v for k, v in _crossings(np.array(r["cv"]["vca"]), step).items()}})
        patch.apply(lab, {"attack": 0})
        for d in (0, 10, 20, 30, 40, 50, 60, 70):
            patch.apply(lab, {"decay": d, "sustain": 0})
            lab.note_on(NOTE)
            r = lab.render(8000 if d >= 50 else 3000, cv_every=1)
            lab.note_off(NOTE)
            lab.step(300)
            v = np.array(r["cv"]["vca"])
            ipk = int(np.argmax(v))
            row = {"knob": d}
            for pct in (50, 10):
                below = np.nonzero(v[ipk:] <= v.max() * pct / 100)[0]
                row[f"down_to_{pct}pct_ms"] = round(float(below[0] * step), 1) if len(below) else None
            out["decay"].append(row)
            patch.apply(lab, {"sustain": 100})
            lab.note_on(NOTE)
            lab.step(300)
            lab.note_off(NOTE)
            r = lab.render(8000 if d >= 50 else 3000, cv_every=1)
            v = np.array(r["cv"]["vca"])
            row = {"knob": d}
            for pct in (50, 10):
                below = np.nonzero(v <= v[0] * pct / 100)[0]
                row[f"down_to_{pct}pct_ms"] = round(float(below[0] * step), 1) if len(below) else None
            out["release"].append(row)
        patch.apply(lab, {"decay": 20})
        for s in (0, 25, 50, 75, 100):
            patch.apply(lab, {"sustain": s})
            lab.note_on(NOTE)
            r = lab.render(3000, cv_every=4)
            lab.note_off(NOTE)
            lab.step(1200)
            v = np.array(r["cv"]["vca"])
            out["sustain"].append({"knob": s, "held_level_vs_peak": round(float(v[-1] / v.max()), 3) if v.max() > 0 else None})
        patch.apply(lab, {"sustain": 0, "decay": 30, "cutoff": 40})
        base = None
        for amt in (-100, -50, 0, 25, 50, 75, 100):
            patch.apply(lab, {"filter_amount": amt})
            lab.step(200)
            rest = lab.cv()["cutoff_16b"]
            lab.note_on(NOTE)
            r = lab.render(1500, cv_every=1)
            lab.note_off(NOTE)
            lab.step(1500)
            c = np.array(r["cv"]["cutoff_16b"], dtype=float)
            extreme = c.max() if amt >= 0 else c.min()
            out["filter_amount"].append({"knob": amt, "rest_cutoff_16b": rest, "extreme_cutoff_16b": int(extreme),
                                         "sweep_octaves": round(float((extreme - rest) / 65535 * 10.71), 2)})
        out["block_ms"] = step
    with open(os.path.join(KB, "envelope.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print("envelope: done")
