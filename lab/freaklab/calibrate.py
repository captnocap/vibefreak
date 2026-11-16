"""Records what the instrument's screen says at each knob position.

A knob's screen only appears when the physical knob moves, so each knob is
set by MIDI, then the emulated pot is nudged a hair to bring the screen up, and
the firmware's stored value is read after the nudge. The result pairs "knob at
N percent" with the exact text the real display would show there.
"""
import json
import os

from . import ocr, params, patch
from .client import Lab

# Filter Amount and Glide are left out: their screens use a different layout
# (Filter Amount is the Env > Cutoff slot of the matrix, Glide is drawn in large type).
POT_KNOBS = ["cutoff", "resonance", "attack", "decay", "sustain",
             "cyc_rise", "cyc_fall", "cyc_hold", "cyc_amount"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb", "panel.json")


def shown_for(lab, knob, cc_value, pos):
    cc, param, bipolar = patch.KNOBS[knob]
    lab.cc(cc, cc_value)
    lab.step(60)
    for d in (6, -6):
        pos[knob] = pos.get(knob, 2048) + d
        lab.pot(knob, pos[knob])
        lab.step(90)
    screen = ocr.read_screen(lab.oled())
    return patch.stored_to_percent(params.read(lab, param), bipolar), screen["label"], screen["value"]


def run(points=None):
    points = points or [0, 4, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 127]
    table = {}
    with Lab() as lab:
        patch.apply(lab, patch.INIT)
        pos = {}
        for knob in POT_KNOBS:
            shown_for(lab, knob, 64, pos)  # first touch only wakes the pot
            rows = []
            for v in points:
                percent, label, shown = shown_for(lab, knob, v, pos)
                rows.append([percent, shown])
            table[knob] = {"label": label, "points": rows}
        patch.apply(lab, patch.INIT)
    return table


if __name__ == "__main__":
    t = run()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(t, open(OUT, "w"), indent=1)
    for knob, d in t.items():
        print(knob, d["label"], " ".join(f"{p}:{s}" for p, s in d["points"]))
