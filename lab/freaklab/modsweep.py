"""Measures modulation: what each source puts out and how far each destination moves.

Sources are watched on the cutoff control signal the firmware sends to the
analog board. A matrix amount of A percent moves that signal by A percent of
its whole range times the source's value, so with a small amount on an
otherwise still filter, the signal is a picture of the source: -1..1 for the
LFO, 0..1 for the envelopes. Nothing here depends on the filter model.

Writes lab/kb/modulation.json.
"""
import json
import os
import tempfile

import numpy as np

from . import analyze, calibrate, matrix, menu, ocr, params, patch
from .client import Lab, note_hz

KB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb")
CUTOFF_OCTAVES = 10.71   # the cutoff signal's whole range, from the screen's own Hz readings
PROBE = 10               # matrix amount used to watch a source
NOTE = 48


def _trace(lab, ms, every=1):
    r = lab.render(ms, cv_every=every)
    return np.array(r["cv"]["cutoff_16b"], float), r["cv"]["step_ms"]


class _Watch:
    """A source routed to cutoff at PROBE percent, read back as the source's own value."""

    def __init__(self, lab, source):
        self.lab, self.source = lab, source
        patch.apply(lab, {"cutoff": 50, "filter_amount": 0})
        matrix.clear(lab)
        lab.step(300)
        self.base = lab.cv()["cutoff_16b"]
        matrix.set_amount(lab, source, "cutoff", PROBE)

    def now(self):
        return (self.lab.cv()["cutoff_16b"] - self.base) / (PROBE * 655.35)

    def run(self, ms, every=1):
        c, step = _trace(self.lab, ms, every)
        return (c - self.base) / (PROBE * 655.35), step

    def done(self):
        matrix.set_amount(self.lab, self.source, "cutoff", 0)


def _period_ms(v, step, level=0.0):
    up = np.nonzero((v[:-1] < level) & (v[1:] >= level))[0]
    return float(np.diff(up).mean() * step) if len(up) > 1 else None


def _fundamental(path):
    """Strongest sine wave in a recording (the note itself, for a sawtooth), in Hz."""
    x = analyze.load(path)
    x = x[len(x) // 4:]
    w = np.hanning(len(x))
    spec = np.abs(np.fft.rfft(x * w, 1 << 19))
    k = int(np.argmax(spec[20:])) + 20
    a, b, c = np.log(spec[k - 1:k + 2] + 1e-12)
    k += 0.5 * (a - c) / (a - 2 * b + c)
    return k * analyze.SR / (1 << 19)


def measure_sources(lab):
    out = {}
    # the envelope held at full sustain is a steady 1.0: check that, then use it as a ruler
    patch.apply(lab, {"attack": 0, "decay": 30, "sustain": 100})
    w = _Watch(lab, "env")
    lab.note_on(NOTE)
    lab.step(500)
    out["env_at_full_sustain"] = round(w.now(), 3)
    lab.note_off(NOTE)
    lab.step(400)
    w.done()

    menu.set_modulation_option(lab, "Press Mode", "Velocity")
    w = _Watch(lab, "pressure")
    rows = []
    for vel in (1, 16, 32, 64, 96, 127):
        lab.note_on(NOTE, vel)
        lab.step(300)
        rows.append([vel, round(w.now(), 3)])
        lab.note_off(NOTE)
        lab.step(300)
    out["velocity"] = rows
    menu.set_modulation_option(lab, "Press Mode", "Aftertouch")
    lab.note_on(NOTE)
    lab.step(300)
    rows = [["none", round(w.now(), 3)]]
    for at in (32, 64, 127):
        lab.midi(0xD0, at)
        lab.step(300)
        rows.append([at, round(w.now(), 3)])
    lab.midi(0xD0, 0)
    lab.note_off(NOTE)
    lab.step(300)
    out["aftertouch_midi_channel_pressure"] = rows
    menu.set_modulation_option(lab, "Press Mode", "Velocity")
    w.done()

    w = _Watch(lab, "key_arp")
    menu.set_key_mode(lab, "linear")
    rows = []
    for n in (24, 36, 48, 60, 72, 84, 96):
        lab.note_on(n)
        lab.step(300)
        rows.append([n, round(w.now(), 4)])
        lab.note_off(n)
        lab.step(200)
    out["key_linear"] = rows
    per_octave = (rows[-1][1] - rows[0][1]) / 6
    out["key_linear_per_octave"] = round(per_octave, 4)
    out["key_cutoff_octaves_per_octave_at_100"] = round(per_octave * CUTOFF_OCTAVES, 3)
    menu.set_modulation_option(lab, "Key/Arp Mode", "Random")
    vals = []
    for _ in range(40):
        lab.note_on(NOTE)
        lab.step(120)
        vals.append(w.now())
        lab.note_off(NOTE)
        lab.step(80)
    out["key_random"] = {"min": round(min(vals), 3), "max": round(max(vals), 3), "same_note_repeats": 40,
                         "distinct_values": len({round(v, 3) for v in vals})}
    menu.set_key_mode(lab, "linear")
    w.done()
    return out


def measure_destinations(lab, tmp):
    """How far a full-scale source (the envelope at full sustain) moves each destination."""
    out = {}
    patch.apply(lab, {"engine": "BasicWaves", "wave": 50, "timbre": 0, "shape": 0, "attack": 0, "sustain": 100,
                      "cutoff": 50, "resonance": 30})
    matrix.clear(lab)
    raw = os.path.join(tmp, "p.wav")

    def pitch_with(amount):
        matrix.set_amount(lab, "env", "pitch", amount)
        patch.play(lab, NOTE, 700, 0, raw_wav=raw, cv_every=0)
        lab.step(300)
        return _fundamental(raw)

    f0 = pitch_with(0)
    rows = []
    for amount in (1, 2, 5, 10, 25, 50, 100, -10, -25, -50):
        hz = pitch_with(amount)
        rows.append([amount, round(hz, 2), round(12 * np.log2(hz / f0), 2)])
    matrix.set_amount(lab, "env", "pitch", 0)
    out["pitch"] = {"note_hz": round(f0, 2), "rows": rows, "columns": ["amount", "hz", "semitones"]}

    lab.step(200)
    base = lab.cv()
    rows = []
    for amount in (10, 25, 50, -25):
        matrix.set_amount(lab, "env", "cutoff", amount)
        lab.note_on(NOTE)
        lab.step(400)
        rows.append([amount, round((lab.cv()["cutoff_16b"] - base["cutoff_16b"]) / 65535 * CUTOFF_OCTAVES, 2)])
        lab.note_off(NOTE)
        lab.step(300)
    matrix.set_amount(lab, "env", "cutoff", 0)
    out["cutoff"] = {"rows": rows, "columns": ["amount", "octaves"]}

    # the oscillator knobs: the firmware's live value while the note is held, in percent of knob travel
    for dest, param, knob in (("wave", "VCO.Param1", "wave"), ("timbre", "VCO.Param2", "timbre")):
        patch.apply(lab, {knob: 50})
        rows = []
        for amount in (10, 25, 50, -25):
            matrix.set_amount(lab, "env", dest, amount)
            lab.note_on(NOTE)
            lab.step(400)
            rows.append([amount, round(params.read(lab, param) * 100 / 32767 - 50, 1)])
            lab.note_off(NOTE)
            lab.step(300)
        matrix.set_amount(lab, "env", dest, 0)
        patch.apply(lab, {knob: 0 if knob == "timbre" else 50})
        out[dest] = {"rows": rows, "columns": ["amount", "knob_percent_moved"]}

    # an Assign column pointed at Shape and at Resonance
    matrix.assign(lab, 1, "shape")
    patch.apply(lab, {"shape": 50})
    rows = []
    for amount in (10, 25, 50, -25):
        matrix.set_amount(lab, "env", "assign1", amount)
        lab.note_on(NOTE)
        lab.step(400)
        rows.append([amount, round(params.read(lab, "VCO.Param3") * 100 / 32767 - 50, 1)])
        lab.note_off(NOTE)
        lab.step(300)
    out["assign_shape"] = {"rows": rows, "columns": ["amount", "knob_percent_moved"]}
    matrix.set_amount(lab, "env", "assign1", 0)
    patch.apply(lab, {"shape": 0})
    matrix.assign(lab, 1, "resonance")
    # resonance: compare the control signal with what the knob alone sends
    knob_dac = {}
    for r in (30, 40, 55, 80):
        patch.apply(lab, {"resonance": r})
        lab.step(200)
        knob_dac[r] = lab.cv()["resonance_dac"]
    patch.apply(lab, {"resonance": 30})
    rows = []
    for amount in (10, 25, 50):
        matrix.set_amount(lab, "env", "assign1", amount)
        lab.note_on(NOTE)
        lab.step(400)
        rows.append([amount, lab.cv()["resonance_dac"]])
        lab.note_off(NOTE)
        lab.step(300)
    matrix.set_amount(lab, "env", "assign1", 0)
    out["assign_resonance"] = {"knob_at_30": True, "rows": rows, "columns": ["amount", "resonance_signal"],
                               "knob_alone_signal": knob_dac}
    matrix.assign(lab, 1, "shape")
    return out


def measure_lfo(lab):
    out = {"shapes": {}, "free_rate": [], "synced": []}
    patch.apply(lab, {"lfo_sync": False, "lfo_rate": 60, "lfo_shape": "sine"})
    w = _Watch(lab, "lfo")
    for shape in patch.BUTTONS["lfo_shape"][2]:
        patch.apply(lab, {"lfo_shape": shape})
        v, step = w.run(2500)
        row = {"min": round(float(v.min()), 3), "max": round(float(v.max()), 3)}
        per = _period_ms(v, step)
        if shape in ("random", "glide"):
            # how often a new value is drawn: count the level changes
            moves = np.nonzero(np.abs(np.diff(v)) > 0.02)[0]
            starts = moves[np.insert(np.diff(moves) > 40 / step, 0, True)] if len(moves) else []
            row["new_value_every_ms"] = round(float(np.diff(starts).mean() * step), 1) if len(starts) > 2 else None
        elif per:
            up = np.nonzero((v[:-1] < 0) & (v[1:] >= 0))[0]
            a, b = up[1], up[2]
            row["period_ms"] = round(per, 1)
            row["one_cycle"] = [round(float(x), 2) for x in np.interp(np.linspace(a, b, 17)[:-1], np.arange(len(v)), v)]
        out["shapes"][shape] = row
    patch.apply(lab, {"lfo_shape": "sine"})
    pos = {}
    for knob in range(0, 101, 10):
        cc = patch.knob_to_cc(knob)
        lab.cc(93, cc)
        lab.step(100)
        lab.enc("lfo_rate", 1)
        lab.step(200)
        lab.enc("lfo_rate", -1)
        lab.step(250)
        shown = ocr.read_screen(lab.oled())["value"]
        lab.cc(93, cc)
        lab.step(100)
        try:
            expect = float(shown.lower().replace("hz", ""))
        except ValueError:
            expect = 1.0
        ms = min(max(3.2 * 1000 / expect, 1500), 40000)
        v, step = w.run(ms, 1 if ms < 8000 else 4)
        per = _period_ms(v, step)
        out["free_rate"].append({"knob": knob, "shown": shown, "measured_hz": round(1000 / per, 3) if per else None})
    # synced: the tempo is the arpeggiator's Rate. Read it off the screen, then time one beat of LFO.
    patch.apply(lab, {"lfo_sync": True})
    patch.set_lfo_div(lab, "1/4")

    def tempo_shown():
        lab.enc("rate", 1)
        lab.step(200)
        lab.enc("rate", -1)
        lab.step(250)
        return ocr.read_screen(lab.oled())

    if tempo_shown()["label"] != "Rate":  # the arpeggiator is on Sync and shows a division: switch it to free
        lab.click("rate", after_ms=300)
    out["tempo"] = []
    bpm = None
    for cc in (0, 27, 54, 91, 127):
        lab.cc(91, cc)
        lab.step(150)
        screen = tempo_shown()
        try:
            bpm = float(screen["value"].lower().replace("bpm", ""))
        except ValueError:
            continue
        beat = 60000 / bpm
        v, step = w.run(beat * 4.4, 1)
        per = _period_ms(v, step)
        out["tempo"].append({"shown": screen["value"], "beat_ms": round(beat, 1), "quarter_ms": round(per, 1) if per else None})
    out["tempo_bpm"] = bpm  # the last one set, which the division timings below use
    for name in patch.LFO_DIVS:
        patch.set_lfo_div(lab, name)
        lab.step(200)
        beats = {"8/1": 32, "4/1": 16, "2/1": 8, "1/1": 4, "1/2": 2}.get(name, 1)
        ms = beats * 60000 / bpm
        v, step = w.run(ms * 2.4 + 300, 4 if ms > 2000 else 1)
        per = _period_ms(v, step)
        out["synced"].append({"division": name, "period_ms": round(per, 1) if per else None})
    lab.cc(91, 0)
    patch.apply(lab, {"lfo_sync": False, "lfo_rate": 60})
    # retrigger: where the wave stands 20 ms after each of eight notes
    for mode in ("OFF", "ON"):
        menu.set_modulation_option(lab, "LFO Retrig", mode)
        vals = []
        for i in range(8):
            lab.note_on(NOTE)
            lab.step(20)
            vals.append(round(w.now(), 2))
            lab.step(130 + 37 * i)
            lab.note_off(NOTE)
            lab.step(90)
        out[f"retrig_{mode.lower()}_value_20ms_after_note"] = vals
    menu.set_modulation_option(lab, "LFO Retrig", "OFF")
    w.done()
    return out


def _first_at(v, step, level, start=0):
    hit = np.nonzero(v[start:] >= level)[0]
    return float(hit[0] * step) if len(hit) else None


def measure_cycling(lab):
    out = {"rise": [], "fall": [], "hold_env_mode": [], "amount": [], "modes": {}}
    patch.apply(lab, {"cyc_mode": "env", "cyc_rise": 20, "cyc_fall": 20, "cyc_hold": 100, "cyc_amount": 100})
    w = _Watch(lab, "cyc_env")
    pos = {}
    calibrate.shown_for(lab, "cyc_rise", 64, pos)
    calibrate.shown_for(lab, "cyc_fall", 64, pos)
    patch.apply(lab, {"cyc_rise": 20, "cyc_fall": 20})

    def secs(text):
        t = text.lower().strip()
        try:
            return float(t[:-2]) if t.endswith("ms") else float(t[:-1]) * 1000
        except ValueError:
            return 1000.0

    # rise: from note-on to the top, Env mode, Hold at full so the top is held
    for knob in range(0, 101, 10):
        _p, _l, shown = calibrate.shown_for(lab, "cyc_rise", patch.knob_to_cc(knob), pos)
        lab.note_on(NOTE)
        v, step = w.run(min(max(secs(shown) * 1.6, 300), 30000), 1)
        lab.note_off(NOTE)
        lab.step(600)
        top = float(v.max())
        out["rise"].append({"knob": knob, "shown": shown, "top": round(top, 3),
                            "to_50pct_ms": _first_at(v, step, 0.5 * top), "to_90pct_ms": _first_at(v, step, 0.9 * top),
                            "to_99pct_ms": _first_at(v, step, 0.99 * top)})
    patch.apply(lab, {"cyc_rise": 0})
    # fall: from note-off back to rest
    for knob in range(0, 101, 10):
        _p, _l, shown = calibrate.shown_for(lab, "cyc_fall", patch.knob_to_cc(knob), pos)
        lab.note_on(NOTE)
        lab.step(300)
        top = w.now()
        lab.note_off(NOTE)
        v, step = w.run(min(max(secs(shown) * 1.6, 300), 30000), 1)
        lab.step(300)
        row = {"knob": knob, "shown": shown, "from": round(top, 3)}
        for pct in (50, 10, 1):
            below = np.nonzero(v <= top * pct / 100)[0]
            row[f"down_to_{pct}pct_ms"] = round(float(below[0] * step), 1) if len(below) else None
        out["fall"].append(row)
    patch.apply(lab, {"cyc_rise": 10, "cyc_fall": 10})
    # Hold knob in Env mode: the level the envelope rests at while the key is down
    for knob in (0, 25, 50, 75, 100):
        patch.apply(lab, {"cyc_hold": knob})
        lab.note_on(NOTE)
        v, step = w.run(2500, 1)
        lab.note_off(NOTE)
        lab.step(500)
        out["hold_env_mode"].append({"knob": knob, "peak": round(float(v.max()), 3), "level_after_2500ms": round(float(v[-1]), 3)})
    patch.apply(lab, {"cyc_hold": 100})
    for knob in (0, 25, 50, 75, 100):
        patch.apply(lab, {"cyc_amount": knob})
        lab.note_on(NOTE)
        lab.step(500)
        out["amount"].append({"knob": knob, "top": round(w.now(), 3)})
        lab.note_off(NOTE)
        lab.step(400)
    patch.apply(lab, {"cyc_amount": 100, "cyc_rise": 30, "cyc_fall": 30, "cyc_hold": 0})
    shown = {k: calibrate.shown_for(lab, k, patch.knob_to_cc(30), pos)[2] for k in ("cyc_rise", "cyc_fall")}
    # the three modes with the same times: what happens with no key, with a key held, and after release
    for mode in ("env", "run", "loop"):
        patch.apply(lab, {"cyc_mode": mode})
        lab.step(1500)
        idle, step = w.run(3000, 1)
        lab.note_on(NOTE)
        held, _ = w.run(3000, 1)
        lab.note_off(NOTE)
        after, _ = w.run(3000, 1)
        row = {}
        for tag, v in (("no_key", idle), ("key_held", held), ("after_release", after)):
            per = _period_ms(v, step, level=0.5 * float(v.max())) if v.max() > 0.05 else None
            row[tag] = {"min": round(float(v.min()), 3), "max": round(float(v.max()), 3),
                        "repeats_every_ms": round(per, 1) if per else None}
        row["value_20ms_after_note_on"] = round(float(held[int(20 / step)]), 3)
        out["modes"][mode] = row
    out["modes_measured_with"] = {"rise_knob": 30, "fall_knob": 30, "hold_knob": 0, "shown": shown}
    # Hold knob in Loop mode: how much it adds to one cycle
    patch.apply(lab, {"cyc_mode": "loop"})
    rows = []
    for knob in (0, 25, 50, 75):
        _p, _l, hold_shown = calibrate.shown_for(lab, "cyc_hold", patch.knob_to_cc(knob), pos)
        lab.note_on(NOTE)
        v, step = w.run(9000, 1)
        lab.note_off(NOTE)
        lab.step(400)
        per = _period_ms(v, step, level=0.5 * float(v.max()))
        rows.append({"knob": knob, "shown": hold_shown, "cycle_ms": round(per, 1) if per else None})
    out["hold_loop_mode"] = rows
    patch.apply(lab, {"cyc_mode": "env", "cyc_hold": 0, "cyc_amount": 0})
    w.done()
    return out


def measure_arp(lab):
    """The arpeggiator's clock: how often it starts a note at a tempo read off the screen."""
    out = {"free_rate": []}
    patch.apply(lab, {"sustain": 0, "decay": 12, "attack": 0})

    def shown():
        lab.enc("rate", 1)
        lab.step(200)
        lab.enc("rate", -1)
        lab.step(250)
        return ocr.read_screen(lab.oled())

    if shown()["label"] != "Rate":
        lab.click("rate", after_ms=300)
    if not params.read(lab, "Arp.Enable"):
        lab.click("arp_seq", after_ms=300)
    for cc in (0, 27, 54, 91, 127):
        lab.cc(91, cc)
        lab.step(150)
        screen = shown()
        try:
            bpm = float(screen["value"].lower().replace("bpm", ""))
        except ValueError:
            continue
        lab.note_on(48)
        lab.note_on(55)
        r = lab.render(60000 / bpm * 6 + 500, cv_every=1)
        lab.note_off(48)
        lab.note_off(55)
        lab.step(400)
        v = np.array(r["cv"]["vca"])
        per = _period_ms(v, r["cv"]["step_ms"], level=0.5 * float(v.max())) if v.max() > 0 else None
        out["free_rate"].append({"shown": screen["value"], "beat_ms": round(60000 / bpm, 1),
                                 "note_every_ms": round(per, 1) if per else None})
    lab.cc(91, 0)
    lab.click("arp_seq", after_ms=300)
    out["switched_off_again"] = params.read(lab, "Arp.Enable") == 0
    return out


PARTS = {"sources": lambda lab, tmp: measure_sources(lab), "destinations": measure_destinations,
         "lfo": lambda lab, tmp: measure_lfo(lab), "cycling_envelope": lambda lab, tmp: measure_cycling(lab),
         "arpeggiator": lambda lab, tmp: measure_arp(lab)}


def run(parts=None):
    """Measure the named parts (all of them by default) and merge them into modulation.json."""
    path = os.path.join(KB, "modulation.json")
    out = json.load(open(path)) if parts and os.path.exists(path) else {}
    out["probe"] = f"sources read from the cutoff control signal with a matrix amount of {PROBE}"
    out["cutoff_octaves_full_range"] = CUTOFF_OCTAVES
    tmp = tempfile.mkdtemp(prefix="freakmod")
    with Lab() as lab:
        for name in parts or list(PARTS):
            patch.apply(lab, patch.INIT)
            lab.step(800)
            out[name] = PARTS[name](lab, tmp)
            print(f"modulation: {name} done", flush=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    return out


if __name__ == "__main__":
    import sys
    run(sys.argv[1:] or None)
