"""Helpers for writing a piece: a clock counted in steps, note and chord names, parts.

A piece file in lab/pieces/ defines build() and returns Piece(...).build().
Nothing here decides anything musical; it only saves arithmetic.

    from freaklab.compose import Piece, chord_notes, note, scale

    def build():
        p = Piece("rain_on_glass", "Rain on Glass", bpm=72, steps_per_beat=4,
                  about="...", structure=["...", "..."])
        lead = p.part("lead", "voice", role="the tune", gain_db=0, pan=0)
        lead.play(step=0, steps=6, pitch="D4", velocity=100)
        ...
        return p.build()

Time is in steps. With steps_per_beat=4 a step is a sixteenth note and a bar of
4/4 is 16 steps; with 3 it is a triplet eighth. Pitches are MIDI numbers or
names ("C4" is 60, "F#3", "Bb2").
"""
import random

from . import instruments
from .client import note_number

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "pentatonic": [0, 2, 4, 7, 9], "minor_pentatonic": [0, 3, 5, 7, 10], "whole_tone": [0, 2, 4, 6, 8, 10],
}
_QUALITIES = {
    "": [0, 4, 7], "m": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "m7b5": [0, 3, 6, 10], "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14], "5": [0, 7],
}
_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note(pitch):
    """'C4' -> 60, 'Bb2' -> 46, 62 -> 62."""
    if isinstance(pitch, int):
        return pitch
    s = str(pitch).strip()
    if len(s) > 2 and s[1] == "b":  # flats: the client spells everything with sharps
        return note_number(s[0] + s[2:]) - 1
    return note_number(s)


def pitch_class(name):
    """'F#' -> 6, 'Bb' -> 10."""
    pc = _LETTERS[name[0].upper()]
    for mark in name[1:]:
        pc += {"#": 1, "b": -1}[mark]
    return pc % 12


def _split(name):
    root = name[:2] if len(name) > 1 and name[1] in "#b" else name[:1]
    quality = name[len(root):]
    if quality not in _QUALITIES:
        raise ValueError(f"chord '{name}': quality is one of {sorted(_QUALITIES)}")
    return root, quality


def chord(name):
    """'Dm7' -> pitch classes [2, 5, 9, 0], root first.

    Qualities: '', m, dim, aug, sus2, sus4, 7, maj7, m7, m7b5, 6, m6, add9, madd9, 5.
    """
    root, quality = _split(name)
    return [(pitch_class(root) + step) % 12 for step in _QUALITIES[quality]]


def nearest(pc, low):
    """The note with pitch class `pc` in the octave that starts at MIDI note `low`."""
    return low + (pc - low) % 12


def chord_notes(name, low):
    """A chord spelled upward from the first root at or above `low`: chord_notes('Dm', 50) -> [50, 53, 57]."""
    root, quality = _split(name)
    base = nearest(pitch_class(root), low)
    return [base + step for step in _QUALITIES[quality]]


def scale(root, mode="major", low=60, octaves=1):
    """The notes of a scale upward from the first `root` at or above `low`: scale('D', 'dorian', 60)."""
    start = nearest(pitch_class(root), low)
    out = [start + 12 * o + step for o in range(octaves) for step in SCALES[mode]]
    return out + [start + 12 * octaves]


class Part:
    def __init__(self, piece, name, fields, role, gain_db, pan, note_range):
        self.piece, self.name, self.fields, self.role = piece, name, fields, role
        self.gain_db, self.pan, self.range = gain_db, pan, note_range
        self.events = []  # (step, steps, midi note, velocity); steps may be fractions

    def play(self, step, steps, pitch, velocity=96):
        """One note: starts at `step`, lasts `steps`. A part is one voice: a later note cuts an earlier one off."""
        self.events.append((step, steps, note(pitch), int(velocity)))
        return self

    def line(self, step, pitches, steps_each, velocity=96, hold=0.92):
        """Notes one after another. `steps_each` is a number or a list; None in `pitches` is a rest.

        `hold` is how much of each slot the note fills (1.0 is fully joined, 0.5 is short and detached).
        """
        lengths = steps_each if isinstance(steps_each, (list, tuple)) else [steps_each] * len(pitches)
        vels = velocity if isinstance(velocity, (list, tuple)) else [velocity] * len(pitches)
        for pitch, n, vel in zip(pitches, lengths, vels):
            if pitch is not None:
                self.play(step, n * hold, pitch, vel)
            step += n
        return step


class Piece:
    def __init__(self, name, title, bpm, steps_per_beat=4, about="", structure=None, reverb_db=-17, tail_ms=3000):
        self.name, self.title, self.about = name, title, about
        self.structure = structure or []
        self.reverb_db, self.tail_ms = reverb_db, tail_ms
        self.step_ms = 60000.0 / bpm / steps_per_beat
        self.stretch = {}  # step -> factor, for slowing down or speeding up
        self.stretch_from = None  # (step, factor): every step from here on, unless set one by one
        self.marks = []    # (step, text) for the structure list, timed when the piece is built
        self.swing = 0.0
        self.parts = []
        self.jitter = None

    def part(self, name, instrument, role="", gain_db=0.0, pan=0.0, **changes):
        """A new part. `instrument` is a name from freaklab.instruments or a whole patch dict of your own.

        Fields can be changed by keyword: cutoff=50, attack=25. A matrix point has a character keywords
        cannot hold, so pass those as a dict: **{"lfo>cutoff": 5, "lfo>pitch": 0.8}.
        """
        changes = {k.replace(":", ">"): v for k, v in changes.items()}  # 'lfo:cutoff' and 'lfo>cutoff' both work
        if isinstance(instrument, dict):
            fields, note_range, kind = dict(instrument, **changes), None, "own"
        else:
            fields = instruments.get(instrument, **changes)
            note_range = instruments.INSTRUMENTS[instrument]["range"]
            kind = instruments.INSTRUMENTS[instrument]["role"]
        p = Part(self, name, fields, role, gain_db, pan, note_range)
        p.kind = kind
        self.parts.append(p)
        return p

    def tempo(self, from_step, to_step=None, start=1.0, end=None):
        """Make steps longer (factor above 1, slower) or shorter (below 1, faster).

        From `from_step` up to `to_step` the factor slides from `start` to `end`. It applies to
        those steps only: afterwards the piece is back at its written tempo. To change tempo and
        stay there, leave `to_step` out: p.tempo(64, start=0.8) is 25 % faster from step 64 on.
        Steps are whole numbers here.
        """
        if to_step is None:
            self.stretch_from = (int(from_step), start)
            return
        end = start if end is None else end
        n = max(1, to_step - from_step - 1)
        for i, s in enumerate(range(int(from_step), int(to_step))):
            self.stretch[s] = start + (end - start) * i / n

    def _factor(self, s):
        if s in self.stretch:
            return self.stretch[s]
        if self.stretch_from and s >= self.stretch_from[0]:
            return self.stretch_from[1]
        return 1.0

    def seconds(self, step):
        """When a step happens, in seconds from the start, with every tempo change so far counted."""
        return self._time(step) / 1000.0

    def clock(self, step):
        """The same as m:ss, for writing the structure lines."""
        t = int(round(self.seconds(step)))
        return f"{t // 60}:{t % 60:02d}"

    def mark(self, step, text):
        """Add a line to the structure list, stamped with the time of `step` when the piece is built
        (so it stays right however the tempo is bent later)."""
        self.marks.append((step, text))

    def set_swing(self, amount):
        """Delay every second step by this fraction of a step (0.0 straight, about 0.33 is a triplet shuffle)."""
        self.swing = amount

    def humanize(self, ms=7, velocity=6, seed=1, parts=None):
        """Nudge note starts and strengths a little, the same way every time for a given seed.

        Notes written on the same step move together, so a unison between two parts stays a
        unison. `velocity` also blurs hand-written accents a little: pass 0 to keep them exact.
        `parts` limits it to the named parts (the rest stay machine-exact).
        """
        self.jitter = (ms, velocity, seed, set(parts) if parts else None)

    def _time(self, step):
        whole = int(step // 1)
        t = sum(self.step_ms * self._factor(s) for s in range(whole))
        t += (step - whole) * self.step_ms * self._factor(whole)
        if self.swing and step == whole and whole % 2 == 1:
            t += self.swing * self.step_ms * self._factor(whole)
        return t

    def build(self):
        """The dict that `freak piece` renders."""
        cache = {}

        def at(step):
            if step not in cache:
                cache[step] = self._time(step)
            return cache[step]

        rng = random.Random(self.jitter[2]) if self.jitter else None
        tracks = []
        for p in self.parts:
            loose = bool(self.jitter) and (self.jitter[3] is None or p.name in self.jitter[3])
            events = []
            for step, steps, pitch, vel in p.events:
                start, end = at(step), at(step + steps)
                if loose:
                    # the timing nudge depends on the step alone, so parts that meet on a step stay together
                    nudge = random.Random(f"{self.jitter[2]}:{step:.4f}").uniform(-self.jitter[0], self.jitter[0])
                    start = max(0.0, start + nudge)
                    if self.jitter[1]:
                        vel = max(1, min(127, vel + rng.randint(-self.jitter[1], self.jitter[1])))
                events.append((start, max(20.0, end - start), pitch, vel))
            tracks.append({"name": p.name, "role": p.role, "kind": getattr(p, "kind", "own"), "fields": p.fields,
                           "events": events, "gain_db": p.gain_db, "pan": p.pan, "range": p.range})
        structure = list(self.structure) + [f"{self.clock(step)} {text}" for step, text in sorted(self.marks)]
        return {"name": self.name, "title": self.title, "about": self.about, "structure": structure,
                "reverb_db": self.reverb_db, "tail_ms": self.tail_ms, "tracks": tracks}
