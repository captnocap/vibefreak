"""Claude's Sonnet, for multitracked MicroFreak.

A Shakespearean sonnet with the words taken out and the form left in:

- Fourteen lines. Each is iambic pentameter: five feet of short-long, ten
  notes, the long ones struck harder. A breath after every line.
- Three quatrains and a couplet, rhymed ABAB CDCD EFEF GG. A rhyme here is
  the last foot of a line: lines that rhyme end on the same two notes.
- The turn comes at line nine, as it should: D minor gives way to F major
  and a bell joins the voice. The couplet answers in D major, and its two
  lines rhyme an octave apart, the last one coming down to rest.

Times are counted in eighth notes; an iamb is one eighth then a quarter.
"""

EIGHTH_MS = 300.0
LINE = 18          # eighths per line: five feet of three, then three for the last note to ring and a breath
INTRO = 12         # eighths of pad and bass before the first line
ENDING = 14        # eighths the last chord is held

# name -> (root, third, fifth) as pitch classes, C = 0
CHORDS = {
    "Dm": (2, 5, 9), "A": (9, 1, 4), "Gm": (7, 10, 2), "C": (0, 4, 7), "F": (5, 9, 0), "Bb": (10, 2, 5),
    "D": (2, 6, 9), "G": (7, 11, 2), "Em": (4, 7, 11), "Bm": (11, 2, 6),
}

# (rhyme, ten notes as MIDI numbers, the chord under each of the five feet)
LINES = [
    # first quatrain: D minor, the thing stated
    ("A", [57, 62, 62, 65, 64, 69, 67, 65, 64, 62], ["Dm", "Dm", "Dm", "Dm", "Dm"]),
    ("B", [62, 65, 65, 69, 69, 72, 70, 69, 67, 69], ["F", "F", "F", "A", "A"]),
    ("A", [69, 74, 72, 70, 69, 67, 65, 67, 64, 62], ["Gm", "Gm", "Gm", "A", "Dm"]),
    ("B", [62, 64, 65, 67, 69, 65, 64, 65, 67, 69], ["C", "C", "F", "Dm", "A"]),
    # second quatrain: it climbs and leans on G minor and B flat
    ("C", [67, 70, 70, 74, 72, 70, 69, 70, 69, 67], ["Gm", "Gm", "Gm", "Gm", "Gm"]),
    ("D", [65, 70, 70, 72, 74, 77, 76, 74, 72, 70], ["Bb", "F", "F", "Bb", "Bb"]),
    ("C", [74, 77, 76, 74, 72, 74, 72, 70, 69, 67], ["Dm", "Dm", "Dm", "Gm", "Gm"]),
    ("D", [67, 69, 70, 72, 74, 72, 70, 74, 72, 70], ["F", "F", "F", "Bb", "Bb"]),
    # third quatrain, the turn: F major, higher, the bell comes in
    ("E", [72, 77, 77, 81, 79, 77, 76, 72, 79, 77], ["F", "F", "F", "C", "F"]),
    ("F", [77, 76, 74, 72, 70, 74, 72, 69, 70, 72], ["C", "C", "Bb", "F", "C"]),
    ("E", [69, 72, 77, 76, 74, 77, 81, 79, 79, 77], ["F", "C", "Dm", "C", "F"]),
    ("F", [77, 74, 72, 69, 70, 72, 74, 70, 70, 72], ["Bb", "F", "C", "Bb", "C"]),
    # couplet: D major; the first line lands on B minor, the second comes home
    ("G", [62, 66, 69, 74, 73, 71, 69, 71, 73, 74], ["D", "D", "G", "Em", "Bm"]),
    ("G", [78, 76, 74, 71, 69, 66, 67, 64, 61, 62], ["A", "G", "D", "A", "D"]),
]

LEAD = {"engine": "Formant", "wave": 0, "timbre": 50, "shape": 67, "cutoff": 62, "resonance": 10,
        "attack": 10, "decay": 38, "sustain": 85,
        "lfo_shape": "sine", "lfo_rate": 60, "lfo>pitch": 0.45,          # a narrow vibrato
        "pressure>timbre": 12, "pressure>cutoff": 10,                      # stressed syllables open the vowel
        "key_arp>cutoff": 50}
BELL = {"engine": "Two Op. FM", "wave": 67, "timbre": 33, "shape": 17, "cutoff": 90, "resonance": 0,
        "attack": 0, "decay": 32, "sustain": 0}
PAD = {"engine": "SuperWave", "wave": 0, "timbre": 45, "shape": 60, "cutoff": 42, "resonance": 12,
       "attack": 30, "decay": 50, "sustain": 90, "lfo_shape": "tri", "lfo_rate": 25, "lfo>cutoff": 3}
BASS = {"engine": "V.Analog", "wave": 0, "timbre": 50, "shape": 0, "cutoff": 38, "resonance": 20,
        "attack": 5, "decay": 35, "sustain": 80, "filter_amount": 10}
LUTE = {"engine": "KarplusStr", "wave": 0, "timbre": 45, "shape": 75, "cutoff": 70, "resonance": 10,
        "decay": 40, "sustain": 100, "pressure>cutoff": 25}


def _in_range(pc, low):
    """The note with pitch class `pc` in the octave starting at MIDI note `low`."""
    return low + (pc - low) % 12


def build():
    # how long each eighth lasts: steady, then the last line slows and the ending is broad
    total = INTRO + LINE * len(LINES) + ENDING
    lengths = [EIGHTH_MS] * total
    last = INTRO + LINE * (len(LINES) - 1)
    for i in range(LINE):
        lengths[last + i] = EIGHTH_MS * (1 + 0.5 * i / (LINE - 1))
    for i in range(last + LINE, total):
        lengths[i] = EIGHTH_MS * 1.5
    starts = [0.0]
    for ms in lengths:
        starts.append(starts[-1] + ms)

    def at(e):
        return starts[e]

    def span(e, n):
        return starts[min(e + n, total)] - starts[e]

    lead, bell, bass, pad_a, pad_b, lute = [], [], [], [], [], []

    # which chord sounds on every eighth of the piece
    chord_at = ["Dm"] * INTRO
    for _rhyme, _notes, chords in LINES:
        for foot in range(5):
            chord_at += [chords[foot]] * 3
        chord_at += [chords[4]] * 3
    chord_at += ["D"] * ENDING

    for n, (_rhyme, notes, _chords) in enumerate(LINES):
        e0 = INTRO + n * LINE
        quiet = 0.88 if n < 4 else 1.0 if n < 12 else 0.94
        if n == 13:
            quiet = 0.85
        for foot in range(5):
            short, long_ = notes[2 * foot], notes[2 * foot + 1]
            e = e0 + 3 * foot
            lead.append((at(e), span(e, 1) * 0.92, short, round(70 * quiet)))
            held = 4 if foot == 4 else 2
            if n == 13 and foot == 4:
                held = 3 + ENDING - 4             # the last note is held under the closing chord
            lead.append((at(e + 1), span(e + 1, held) * (0.97 if foot == 4 else 0.95), long_, round(112 * quiet)))
            if 8 <= n < 12:                       # the bell doubles the stressed notes of the turn
                bell.append((at(e + 1), span(e + 1, 2), long_, 92))
            elif n >= 12 and foot == 4:           # and marks the couplet's rhyme
                bell.append((at(e + 1), span(e + 1, 4), long_ + (12 if n == 13 else 0), 100))

    # bass and pad: a new note whenever the chord changes, and at least one per half line
    def sustained(track, pick, velocity, restrike_every=9):
        e = 0
        while e < total:
            chord = chord_at[e]
            run = 1
            while e + run < total and chord_at[e + run] == chord and run < restrike_every and (e + run - INTRO) % LINE != 0:
                run += 1
            track.append((at(e), span(e, run) - 30, pick(chord), velocity))
            e += run

    sustained(bass, lambda c: _in_range(CHORDS[c][0], 36), 96)
    sustained(pad_a, lambda c: _in_range(CHORDS[c][1], 53), 84, restrike_every=LINE)
    sustained(pad_b, lambda c: _in_range(CHORDS[c][2], 53), 84, restrike_every=LINE)

    # the plucked string walks each chord in eighths from the second quatrain on, leaning on the long syllable
    for e in range(INTRO + 4 * LINE, last + 15):
        root, third, fifth = CHORDS[chord_at[e]]
        low = _in_range(root, 45)
        step = (e - INTRO) % 3
        note = [low, low + (fifth - root) % 12, low + 12 + (third - root) % 12][step]
        lute.append((at(e), span(e, 1) * 1.6, note, [62, 104, 80][step]))
    # last chord, spread upward
    e_end = last + LINE
    for i, note in enumerate((50, 57, 62, 66)):
        lute.append((at(e_end) + i * 150, 2400, note, 96))
    bell.append((at(e_end) + 650, 3000, 86, 84))

    return {
        "name": "claudes_sonnet",
        "title": "Claude's Sonnet",
        "about": ("A sonnet with the words taken out and the form left in: fourteen lines of five short-long feet, "
                  "rhymed ABAB CDCD EFEF GG by how each line ends, with the turn at line nine and a couplet "
                  "that comes home in D major."),
        "structure": [
            "Lines 1-4 (ABAB): D minor. The voice alone over pad and bass.",
            "Lines 5-8 (CDCD): it climbs; a plucked string starts walking the chords.",
            "Lines 9-12 (EFEF), the turn: F major, higher, a bell on every stressed note.",
            "Lines 13-14 (GG): D major. Both lines end C sharp to D, an octave apart; the last one slows and comes down to rest.",
            "A rhyme is the last foot of a line: lines with the same letter end on the same two notes.",
        ],
        "reverb_db": -17,
        "tail_ms": 3500,
        "tracks": [
            {"name": "voice", "role": "the line itself", "fields": LEAD, "events": lead, "gain_db": 0, "pan": 0.0},
            {"name": "bell", "role": "stressed notes of the turn, the couplet's rhyme", "fields": BELL, "events": bell, "gain_db": -7, "pan": 0.4},
            {"name": "pad_third", "role": "the third of each chord", "fields": PAD, "events": pad_a, "gain_db": -7, "pan": -0.55},
            {"name": "pad_fifth", "role": "the fifth of each chord", "fields": PAD, "events": pad_b, "gain_db": -7, "pan": 0.55},
            {"name": "bass", "role": "the root of each chord", "fields": BASS, "events": bass, "gain_db": -5, "pan": 0.0},
            {"name": "string", "role": "plucked chord tones in eighths, from line 5", "fields": LUTE, "events": lute, "gain_db": -8, "pan": -0.3},
        ],
    }
