"""A patch in panel terms, and how to put one on the emulated instrument.

Every continuous control is a knob position in percent of its travel (0 = hard
left, 100 = hard right). They are sent as MIDI control changes, which the
firmware treats as absolute, so there are 128 positions per knob. Buttons are
clicked until the firmware reports the wanted state. After applying, the
firmware's own parameter table is read back and returned, so what a recording
is labelled with is what the firmware actually held.
"""
from . import engines, ocr, params

# knob name -> (MIDI CC, firmware parameter, bipolar)
KNOBS = {
    "wave": (10, "VCO.Param1", False),
    "timbre": (12, "VCO.Param2", False),
    "shape": (13, "VCO.Param3", False),
    "cutoff": (23, "VCF.Cutoff", False),
    "resonance": (83, "VCF.Reso", False),
    "attack": (105, "EG2.Attack", False),
    "decay": (106, "EG2.DecRel", False),
    "sustain": (29, "EG2.Sustain", False),
    "filter_amount": (26, "EG2.Amount", True),
    "cyc_rise": (102, "EG1.RiseLvl", False),
    "cyc_fall": (103, "EG1.FallLvl", False),
    "cyc_hold": (28, "EG1.Hold", False),
    "cyc_amount": (24, "EG1.Amount", False),
    "glide": (5, "Kbd.Glide", False),
    "lfo_rate": (93, "LFO.Rate", False),
}

# button name -> (firmware parameter, {state name: stored value})
BUTTONS = {
    "filter": ("filter_type", "VCF.Type", {"lp": 0, "bp": 16384, "hp": 32767}),
    "amp_mod": ("amp_mod", "EG2.Mode", {False: 0, True: 32767}),
    "cyc_mode": ("cyc_mode", "EG1.Mode", {"env": 0, "run": 16384, "loop": 32767}),
    "paraphonic": ("paraphonic", "Gen.Parafon", {False: 0, True: 32767}),
}

# A plain starting point: one oscillator straight through an open filter, organ-style envelope.
INIT = {
    "engine": "BasicWaves",
    "wave": 50, "timbre": 50, "shape": 0,
    "cutoff": 100, "resonance": 0, "filter": "lp",
    "attack": 0, "decay": 30, "sustain": 100, "filter_amount": 0, "amp_mod": True,
    "cyc_mode": "env", "cyc_rise": 20, "cyc_fall": 20, "cyc_hold": 0, "cyc_amount": 0,
    "glide": 0, "paraphonic": False,
}


class PatchError(RuntimeError):
    pass


def knob_to_cc(percent, bipolar=False):
    if bipolar:  # -100..100 around the 12 o'clock position
        return max(0, min(127, round(64 + percent * 63 / 100)))
    return max(0, min(127, round(percent * 127 / 100)))


def stored_to_percent(value, bipolar=False):
    if bipolar:
        return round((value - 16383.5) / 163.835, 1)
    return round(value * 100 / 32767, 1)


def set_engine(lab, name):
    eng = engines.lookup(name)
    for _ in range(3):
        lab.cc(9, engines.type_cc(eng))
        lab.step(350)
        if engines.index_of(params.read(lab, "VCO.Type")) == eng[1]:
            return eng
    raise PatchError(f"could not select oscillator type {eng[0]}")


def set_button(lab, name, state):
    switch, param, states = BUTTONS[name]
    if state not in states:
        raise PatchError(f"{name} must be one of {list(states)}")
    for _ in range(len(states) + 1):
        if params.read(lab, param) == states[state]:
            return
        lab.click(switch)
        lab.step(120)
    raise PatchError(f"could not set {name} to {state}")


def apply(lab, patch):
    """Set every control named in `patch` (anything missing is left alone)."""
    unknown = set(patch) - set(KNOBS) - set(BUTTONS) - {"engine"}
    if unknown:
        raise PatchError(f"unknown patch fields: {sorted(unknown)}")
    if "engine" in patch:
        set_engine(lab, patch["engine"])
    for name, (cc, _param, bipolar) in KNOBS.items():
        if name in patch:
            lab.cc(cc, knob_to_cc(patch[name], bipolar))
    for name in BUTTONS:
        if name in patch:
            set_button(lab, name, patch[name])
    lab.step(120)


def read_back(lab):
    """The patch as the firmware holds it, in the same terms `apply` takes."""
    raw = params.read_all(lab)
    eng = engines.BY_INDEX.get(engines.index_of(raw["VCO.Type"]))
    out = {"engine": eng[0] if eng else f"type {raw['VCO.Type']}"}
    for name, (_cc, param, bipolar) in KNOBS.items():
        out[name] = stored_to_percent(raw[param], bipolar)
    for name, (_switch, param, states) in BUTTONS.items():
        out[name] = next((s for s, v in states.items() if v == raw[param]), raw[param])
    return out


def osc_display(lab):
    """What the screen says for Wave, Timbre and Shape (label and value as shown).

    The screen only shows a parameter when its knob is touched, so each encoder
    is nudged one click and back, and the stored value is put back exactly. The
    label read is checked against the one this oscillator type should show, so a
    screen that had not caught up yet is never mistaken for the answer.
    """
    eng = engines.BY_INDEX.get(engines.index_of(params.read(lab, "VCO.Type")))
    out = {}
    for i, (enc, param) in enumerate((("wave", "VCO.Param1"), ("timbre", "VCO.Param2"), ("shape", "VCO.Param3"))):
        before = params.read(lab, param)
        first = -1 if before >= 32767 - 64 else 1
        expected = eng[3][i] if eng else None
        screen = {"label": "", "value": ""}
        for wait in (120, 250, 500):
            lab.step(wait)
            lab.enc(enc, first)
            lab.step(wait)
            lab.enc(enc, -first)
            lab.step(wait + 60)
            screen = ocr.read_screen(lab.oled())
            if expected is None or screen["label"] == expected:
                break
        cc, _p, _b = KNOBS[enc]
        if params.read(lab, param) != before:
            lab.cc(cc, round(before * 127 / 32767))
            lab.step(40)
        ok = expected is None or screen["label"] == expected
        out[enc] = {"label": expected or screen["label"], "shown": screen["value"] if ok else None}
    return out


def play(lab, note="C3", hold_ms=1000, release_ms=400, velocity=100, wav=None, raw_wav=None, cv_every=4):
    """Hold one note, release it, and record both phases into one file each."""
    from .client import note_number
    n = note_number(note)
    lab.note_on(n, velocity)
    total = hold_ms + release_ms
    # Render in two calls so the note-off lands on time, then stitch.
    import os, tempfile, wave as wavmod
    tmp = tempfile.mkdtemp(prefix="freak")
    parts = []
    cv = None
    for i, ms in enumerate((hold_ms, release_ms)):
        if i == 1:
            lab.note_off(n)
        if ms <= 0:
            continue
        p = os.path.join(tmp, f"p{i}.wav")
        r = os.path.join(tmp, f"r{i}.wav")
        res = lab.render(ms, wav=p, raw_wav=r, cv_every=cv_every)
        parts.append((p, r))
        if "cv" in res:
            if cv is None:
                cv = res["cv"]
            else:
                for k in ("cutoff_16b", "resonance_dac", "vca", "model_cutoff_hz"):
                    cv[k] += res["cv"][k]
    if release_ms <= 0:
        lab.note_off(n)

    def stitch(paths, dest):
        if not dest:
            return
        with wavmod.open(dest, "wb") as out:
            for i, p in enumerate(paths):
                with wavmod.open(p, "rb") as src:
                    if i == 0:
                        out.setparams(src.getparams())
                    out.writeframes(src.readframes(src.getnframes()))

    stitch([p for p, _ in parts], wav)
    stitch([r for _, r in parts], raw_wav)
    for p, r in parts:
        os.remove(p)
        os.remove(r)
    os.rmdir(tmp)
    return {"note": n, "hold_ms": hold_ms, "release_ms": release_ms, "total_ms": total, "cv": cv}
