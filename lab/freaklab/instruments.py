"""Instruments for pieces: patches that have been played and measured, by the job they do.

Each entry is a patch (the fields `freak play` takes), the range of MIDI notes
it was checked over, and a line on what it sounds like, written from the
measurements rather than from the oscillator type's name. `freak instruments`
lists them; `freak instruments --check` plays every one again and reports
tuning, brightness and how the loudness moves, which is how to vet a new one
before a piece relies on it.

A piece may change any field of an instrument (darker, slower attack, more
vibrato) or use a patch of its own; these are starting points that are known
to be in tune and to behave as described.
"""

INSTRUMENTS = {
    # ---- voices that carry a melody --------------------------------------------------
    "voice": {
        "role": "lead", "range": (55, 81),
        "sounds": "a wordless sung vowel with a narrow vibrato; harder notes open the vowel",
        "fields": {"engine": "Formant", "wave": 0, "timbre": 50, "shape": 67, "cutoff": 62, "resonance": 10,
                   "attack": 10, "decay": 38, "sustain": 85, "lfo_shape": "sine", "lfo_rate": 60, "lfo>pitch": 0.45,
                   "pressure>timbre": 12, "pressure>cutoff": 10, "key_arp>cutoff": 50},
    },
    "reed": {
        "role": "lead", "range": (48, 84),
        "sounds": "a plain, slightly hollow reed, steady and unshowy; sits behind or in front as needed",
        "fields": {"engine": "BasicWaves", "wave": 62, "timbre": 30, "shape": 0, "cutoff": 55, "resonance": 18,
                   "attack": 12, "decay": 35, "sustain": 80, "filter_amount": 10, "key_arp>cutoff": 50},
    },
    "flute": {
        "role": "lead", "range": (60, 96),
        "sounds": "almost a pure sine with a slow breath of vibrato; soft, distant, childlike",
        "fields": {"engine": "Harm", "wave": 0, "timbre": 17, "shape": 0, "cutoff": 75, "resonance": 0,
                   "attack": 18, "decay": 35, "sustain": 90, "lfo_shape": "sine", "lfo_rate": 58, "lfo>pitch": 0.3},
    },
    "saw_lead": {
        "role": "lead", "range": (48, 84),
        "sounds": "a bright sawtooth with a little filter bite on each note; forward, urgent, synth-like",
        "fields": {"engine": "BasicWaves", "wave": 50, "timbre": 0, "shape": 0, "cutoff": 58, "resonance": 28,
                   "attack": 2, "decay": 30, "sustain": 75, "filter_amount": 22, "key_arp>cutoff": 50,
                   "pressure>cutoff": 12},
    },
    "organ": {
        "role": "lead", "range": (43, 84),
        "sounds": "a hollow, churchy organ tone, perfectly steady; solemn or eerie depending on register",
        "fields": {"engine": "Harmo", "wave": 0, "timbre": 33, "shape": 0, "cutoff": 68, "resonance": 0,
                   "attack": 6, "decay": 30, "sustain": 100},
    },
    # ---- struck and plucked things ----------------------------------------------------
    "bell": {
        "role": "keys", "range": (60, 96),
        "sounds": "a clear struck bell that rings for a second or two and dies",
        "fields": {"engine": "Two Op. FM", "wave": 67, "timbre": 33, "shape": 17, "cutoff": 90, "resonance": 0,
                   "attack": 0, "decay": 32, "sustain": 0},
    },
    "keys": {
        "role": "keys", "range": (43, 84),
        "sounds": "a soft electric-piano note: a gentle knock, then a rounded tone that fades",
        "fields": {"engine": "Two Op. FM", "wave": 67, "timbre": 17, "shape": 0, "cutoff": 70, "resonance": 0,
                   "attack": 0, "decay": 34, "sustain": 20, "pressure>cutoff": 15},
    },
    "chime": {
        "role": "keys", "range": (55, 91),
        "sounds": "a bright mallet on metal or glass, shimmering as it dies",
        "fields": {"engine": "Modal", "wave": 33, "timbre": 33, "shape": 67, "cutoff": 90, "resonance": 0,
                   "attack": 0, "decay": 40, "sustain": 100},
    },
    "string": {
        "role": "keys", "range": (40, 72),
        "sounds": "a plucked string, bright at the pluck and brighter when struck harder",
        "fields": {"engine": "KarplusStr", "wave": 0, "timbre": 45, "shape": 75, "cutoff": 70, "resonance": 10,
                   "decay": 40, "sustain": 100, "pressure>cutoff": 25},
    },
    # ---- things that hold a chord tone -------------------------------------------------
    "pad_warm": {
        "role": "pad", "range": (45, 72),
        "sounds": "a dark, thick, slowly swelling pad",
        "fields": {"engine": "SuperWave", "wave": 0, "timbre": 45, "shape": 60, "cutoff": 42, "resonance": 12,
                   "attack": 30, "decay": 50, "sustain": 90, "lfo_shape": "tri", "lfo_rate": 25, "lfo>cutoff": 3, "key_arp>cutoff": 50},
    },
    "pad_wide": {
        "role": "pad", "range": (45, 72),
        "sounds": "a brighter pad whose colour keeps shifting while it is held; glassy, restless",
        "fields": {"engine": "Wavetable", "wave": 33, "timbre": 50, "shape": 83, "cutoff": 55, "resonance": 10,
                   "attack": 35, "decay": 52, "sustain": 90, "key_arp>cutoff": 50},
    },
    # ---- low end ------------------------------------------------------------------------
    "bass_hollow": {
        "role": "bass", "range": (28, 55),
        "sounds": "a round, hollow bass with a little pluck from the filter",
        "fields": {"engine": "V.Analog", "wave": 0, "timbre": 50, "shape": 0, "cutoff": 38, "resonance": 20,
                   "attack": 5, "decay": 35, "sustain": 80, "filter_amount": 10},
    },
    "bass_sub": {
        "role": "bass", "range": (28, 52),
        "sounds": "a pure low sine: felt more than heard, no edge at all",
        "fields": {"engine": "Harm", "wave": 0, "timbre": 0, "shape": 0, "cutoff": 60, "resonance": 0,
                   "attack": 4, "decay": 30, "sustain": 95},
    },
    "bass_dark": {
        "role": "bass", "range": (28, 55),
        "sounds": "a dark bass with some grit in it; heavier and closer than the hollow one",
        "fields": {"engine": "Bass", "wave": 17, "timbre": 0, "shape": 17, "cutoff": 45, "resonance": 15,
                   "attack": 2, "decay": 32, "sustain": 85, "filter_amount": 12},
    },
    # ---- drums and air (the note played hardly matters for the noise ones) -------------
    "kick": {
        "role": "drum", "range": (33, 43),
        "sounds": "a soft thud that drops in pitch as it lands; play it around MIDI 36",
        "fields": {"engine": "Harm", "wave": 0, "timbre": 0, "shape": 0, "cutoff": 62, "resonance": 0,
                   "attack": 0, "decay": 16, "sustain": 0, "env>pitch": 35},
    },
    "snare": {
        "role": "drum", "range": (55, 65),
        "sounds": "a short burst of band-passed noise; a brushed snare or a clap of static",
        "fields": {"engine": "Noise", "wave": 0, "timbre": 100, "shape": 0, "filter": "bp", "cutoff": 66,
                   "resonance": 25, "attack": 0, "decay": 14, "sustain": 0},
    },
    "hat": {
        "role": "drum", "range": (60, 72),
        "sounds": "a tick of high hiss; closed hi-hat",
        "fields": {"engine": "Noise", "wave": 0, "timbre": 100, "shape": 0, "filter": "hp", "cutoff": 88,
                   "resonance": 0, "attack": 0, "decay": 7, "sustain": 0},
    },
    "wind": {
        "role": "texture", "range": (55, 65),
        "sounds": "noise through a slowly wandering filter: wind, surf, breath. Hold long notes",
        "fields": {"engine": "Noise", "wave": 0, "timbre": 100, "shape": 0, "filter": "lp", "cutoff": 55,
                   "resonance": 45, "attack": 45, "decay": 55, "sustain": 85,
                   "lfo_shape": "glide", "lfo_rate": 35, "lfo>cutoff": 12},
    },
}


def get(name, **changes):
    """An instrument's patch, with any fields changed: get('voice', cutoff=50, **{'lfo>pitch': 0.8})."""
    if name not in INSTRUMENTS:
        raise KeyError(f"no instrument '{name}': {sorted(INSTRUMENTS)}")
    fields = dict(INSTRUMENTS[name]["fields"])
    fields.update(changes)
    return fields


def _check_one(job):
    import os
    import tempfile

    from . import analyze, panel, patch
    from .client import Lab, note_hz
    name, note = job
    tmp = tempfile.mkdtemp(prefix="freakinst")
    wav, raw = os.path.join(tmp, "o.wav"), os.path.join(tmp, "r.wav")
    try:
        with Lab() as lab:
            patch.apply(lab, patch.INIT)
            panel.set_and_describe(lab, INSTRUMENTS[name]["fields"])
            patch.play(lab, note, 900, 600, velocity=100, wav=wav, raw_wav=raw, cv_every=0)
        import numpy as np
        x = analyze.load(wav)
        peak = round(float(20 * np.log10(max(float(np.max(np.abs(x))), 1e-6))), 1)
        osc = analyze.analyze_file(raw, note_hz(note), 900, oscillator_only=True)
        out = analyze.analyze_file(wav, note_hz(note), 900)
    except Exception as e:  # a patch the firmware would not take is a finding, not a crash
        return name, note, {"error": str(e)}
    finally:
        for f in (wav, raw):
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(tmp)
    if out.get("silent"):
        return name, note, {"silent": True}
    return name, note, {"cents": osc.get("cents_off"), "peak_db": peak, "level_db": round(out["level_db"], 1),
                        "brightness": out.get("centroid_harm"), "attack_ms": out.get("attack_ms"),
                        "held_vs_start": out.get("sustain_ratio"), "words": out.get("words", [])}


def check(names=None, jobs=12):
    """Play every instrument at the bottom, middle and top of its range and return what was measured."""
    from multiprocessing import Pool
    names = names or list(INSTRUMENTS)
    todo = []
    for n in names:
        lo, hi = INSTRUMENTS[n]["range"]
        todo += [(n, lo), (n, (lo + hi) // 2), (n, hi)]
    with Pool(min(jobs, len(todo))) as pool:
        return pool.map(_check_one, todo)
