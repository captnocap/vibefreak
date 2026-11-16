"""The oscillator types of firmware 5.0, as the instrument's own screen names them.

`index` is the firmware's type number (the stored Type value is index * 32767 / 22).
`cc` is a MIDI CC 9 value in the middle of the range that selects the type
(found by trying all 128 values; the mapping has no memory of where it came from). `params` are the screen labels of the Wave, Timbre
and Shape knobs for that type. All of it was read off the emulated display, not
taken from a manual.

`faithful` is False where the emulator cannot stand in for the real instrument:
the three grain types and Sample play Arturia's factory samples, which are not
part of the firmware download (the emulator substitutes its own synthetic
sounds), and the Vocoder needs a microphone signal.
"""

ENGINES = [
    # name, index, cc, (wave, timbre, shape), faithful
    ("BasicWaves", 1, 5, ("Morph", "Sym", "Sub"), True),
    ("SuperWave", 2, 14, ("Wave", "Detune", "Volume"), True),
    ("Wavetable", 3, 19, ("Table", "Position", "Chorus"), True),
    ("Harmo", 4, 25, ("Content", "Sculpting", "Chorus"), True),
    ("KarplusStr", 5, 30, ("Bow", "Position", "Decay"), True),
    ("V.Analog", 6, 36, ("Detune", "Shape", "Wave"), True),
    ("Waveshaper", 7, 41, ("Wave", "Amount", "Asym"), True),
    ("Two Op. FM", 8, 47, ("Ratio", "Amount", "Feedback"), True),
    ("Formant", 9, 52, ("Interval", "Formant", "Shape"), True),
    ("Chords", 10, 58, ("Type", "Inv/Trsp", "Waveform"), True),
    ("Speech", 11, 63, ("Type", "Timbre", "Word"), True),
    ("Modal", 12, 69, ("Inharm", "Timbre", "Decay"), True),
    ("Noise", 13, 74, ("Type", "Rate", "Balance"), True),
    ("Bass", 15, 80, ("Saturate", "Fold", "Noise"), True),
    ("SawX", 16, 85, ("SawMod", "Shape", "Noise"), True),
    ("Harm", 17, 91, ("Spread", "Rectify", "Noise"), True),
    ("WaveUser", 18, 96, ("Table", "Position", "Bitdepth"), True),
    ("Sample", 19, 102, ("Start", "Length", "Loop"), False),
    ("Scan Grains", 20, 107, ("Scan", "Density", "Chaos"), False),
    ("Cloud Grains", 21, 113, ("Start", "Density", "Chaos"), False),
    ("Hit Grains", 22, 118, ("Start", "Density", "Shape"), False),
    ("Vocoder", 14, 124, ("Wave", "Shift", "Bandwidth"), False),
]

BY_NAME = {e[0].lower().replace(" ", "").replace(".", ""): e for e in ENGINES}
BY_INDEX = {e[1]: e for e in ENGINES}


def lookup(name):
    key = str(name).lower().replace(" ", "").replace(".", "").replace("_", "").replace("-", "")
    if key in BY_NAME:
        return BY_NAME[key]
    hits = [e for k, e in BY_NAME.items() if k.startswith(key)]
    if len(hits) == 1:
        return hits[0]
    raise KeyError(f"unknown oscillator type '{name}'; one of: " + ", ".join(e[0] for e in ENGINES))


def type_cc(engine):
    return engine[2]


def index_of(type_value):
    return round(type_value * 22 / 32767)
