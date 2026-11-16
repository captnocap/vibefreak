"""Plays whole pieces: several one-voice tracks, each its own patch, mixed to stereo.

The MicroFreak plays one patch at a time, so a piece is made the way it would
be with the real instrument and a recorder: each part is played through on its
own patch, start to finish, and the takes are laid over each other. Every note
of every take comes out of the emulated instrument; the mix adds only level,
left-right placement and, if asked, a room reverb (which is not the synth, and
is said so on the listening page).

A piece is a dict:
  {"name", "title", "about", "structure": [lines of text], "reverb_db": -17 or None,
   "tracks": [{"name", "role", "fields": patch fields, "gain_db", "pan" (-1..1),
               "events": [(start_ms, length_ms, midi_note, velocity), ...]}]}
"""
import datetime
import json
import os
import tempfile
import wave
from multiprocessing import Pool

import numpy as np

from . import panel, patch
from .client import Lab

SR_IN = 96000
SR_OUT = 48000
GAP_MS = 12  # a held note is let go this long before the next one, so each note starts its envelope


def _read(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def render_track(job):
    """One take: set the patch, play the events in time, return the recording as float samples at 96 kHz."""
    track, total_ms = job
    events = sorted(track["events"])
    actions = []
    for i, (start, length, note, vel) in enumerate(events):
        end = start + length
        if i + 1 < len(events):
            end = min(end, events[i + 1][0] - GAP_MS)
        if end <= start:
            raise ValueError(f"{track['name']}: note at {start} ms has no room before the next one")
        actions.append((start, 1, note, vel))
        actions.append((end, 0, note, 0))
    actions.sort(key=lambda a: (a[0], a[1]))  # at the same instant, let go before striking
    tmp = tempfile.mkdtemp(prefix="freakscore")
    seg = os.path.join(tmp, "seg.wav")
    chunks, pos = [], 0
    with Lab() as lab:
        patch.apply(lab, patch.INIT)
        back, _shown, lines = panel.set_and_describe(lab, track["fields"])
        lab.step(400)

        def advance(to_ms):
            nonlocal pos
            target = round(to_ms * SR_IN / 1000)
            if target - pos >= 32:
                lab.render((target - pos) * 1000 / SR_IN, wav=seg)
                data = _read(seg)
                chunks.append(data)
                pos += len(data)

        for t, on, note, vel in actions:
            advance(t)
            if on:
                lab.note_on(note, vel)
            else:
                lab.note_off(note)
        advance(total_ms)
    os.remove(seg)
    os.rmdir(tmp)
    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    return track["name"], audio, lines


def _fft_convolve(x, h):
    n = len(x) + len(h) - 1
    size = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(h, size), size)[:n]


def _halve(x):
    """96 kHz to 48 kHz: low-pass below 22 kHz, then keep every second sample."""
    taps = 255
    n = np.arange(taps) - (taps - 1) / 2
    h = 0.46 * np.sinc(0.46 * n) * np.blackman(taps)
    h /= h.sum()
    y = _fft_convolve(x, h)[(taps - 1) // 2:(taps - 1) // 2 + len(x)]
    return y[::2]


def _room(seconds=2.2, decay=0.33, seed=7):
    """A plain room: two channels of noise dying away, darker as it goes. Not a model of any real space."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR_OUT)
    t = np.arange(n) / SR_OUT
    out = []
    for _ in range(2):
        noise = rng.standard_normal(n)
        # one-pole low-pass by cumulative blend, which takes the fizz off the tail
        k = np.exp(-2 * np.pi * 3500 / SR_OUT)
        spec = np.fft.rfft(noise)
        f = np.fft.rfftfreq(n, 1 / SR_OUT)
        spec *= (1 - k) / np.abs(1 - k * np.exp(-2j * np.pi * f / SR_OUT))
        tail = np.fft.irfft(spec, n) * np.exp(-t / decay)
        tail[: int(0.018 * SR_OUT)] = 0  # a short gap before the room answers
        out.append(tail / np.sqrt(np.sum(tail ** 2)))
    return out


def mix(piece, takes):
    """Lay the takes over each other in stereo at 48 kHz. Returns (left, right, per-track levels in dB)."""
    left = right = None
    levels = {}
    for track in piece["tracks"]:
        x = _halve(takes[track["name"]])
        peak = float(np.max(np.abs(x))) or 1.0
        x = x / peak * 10 ** (track.get("gain_db", 0) / 20)
        frames = x[: len(x) // 2400 * 2400].reshape(-1, 2400) ** 2  # 50 ms frames
        power = frames.mean(axis=1)
        sounding = power[power > power.max() * 1e-4] if power.size and power.max() > 0 else power
        levels[track["name"]] = round(float(10 * np.log10(sounding.mean() + 1e-12)), 1) if sounding.size else -99.0
        angle = (track.get("pan", 0) + 1) * np.pi / 4  # equal power
        l, r = x * np.cos(angle), x * np.sin(angle)
        left = l if left is None else left + l
        right = r if right is None else right + r
    wet = piece.get("reverb_db")
    if wet is not None:
        ir_l, ir_r = _room()
        mono = (left + right) / 2
        g = 10 ** (wet / 20)
        n = len(left) + int(1.2 * SR_OUT)
        pad = np.zeros(n - len(left))
        left = np.concatenate([left, pad]) + g * _fft_convolve(mono, ir_l)[:n]
        right = np.concatenate([right, pad]) + g * _fft_convolve(mono, ir_r)[:n]
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right)))) or 1.0
    scale = 10 ** (-1 / 20) / peak
    return left * scale, right * scale, levels


def render_piece(piece, out_dir, jobs=8):
    total_ms = max(s + l for t in piece["tracks"] for s, l, _n, _v in t["events"]) + piece.get("tail_ms", 2500)
    with Pool(min(jobs, len(piece["tracks"]))) as pool:
        results = pool.map(render_track, [(t, total_ms) for t in piece["tracks"]])
    shortest = min(len(audio) for _, audio, _ in results)  # takes can differ by one audio block
    takes = {name: audio[:shortest] for name, audio, _ in results}
    lines = {name: ln for name, _, ln in results}
    left, right, levels = mix(piece, takes)
    base = os.path.join(out_dir, piece["name"])
    stereo = np.empty(2 * len(left), dtype=np.int16)
    stereo[0::2] = np.clip(left * 32767, -32768, 32767).astype(np.int16)
    stereo[1::2] = np.clip(right * 32767, -32768, 32767).astype(np.int16)
    with wave.open(base + ".wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR_OUT)
        w.writeframes(stereo.tobytes())
    card = {
        "kind": "piece", "name": piece["name"], "title": piece["title"], "about": piece.get("about", ""),
        "made": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "seconds": round(len(left) / SR_OUT, 1), "structure": piece.get("structure", []),
        "mix": ("Each part is its own take on the emulated MicroFreak. The mix adds level and left-right placement"
                + (f", and a plain room reverb at {piece['reverb_db']} dB, which is not the synth." if piece.get("reverb_db") is not None else ".")),
        "tracks": [{"name": t["name"], "role": t.get("role", ""), "notes": len(t["events"]),
                    "gain_db": t.get("gain_db", 0), "pan": t.get("pan", 0), "level_db": levels[t["name"]],
                    "panel": lines[t["name"]]} for t in piece["tracks"]],
    }
    with open(base + ".json", "w") as fh:
        json.dump(card, fh, indent=1)
    return base + ".wav", takes, card


def check_tuning(piece, takes, min_ms=300):
    """Worst and average pitch error per part, in cents, over the notes long enough to measure.

    Drums and noise textures have no pitch to check and are left out; a pitched part with no
    note long enough is reported as such rather than silently missing.
    """
    out = {}
    for track in piece["tracks"]:
        if track.get("kind") in ("drum", "texture"):
            continue
        out[track["name"]] = "no note long enough to measure"
        x = takes[track["name"]]
        errs = []
        events = sorted(track["events"])
        for i, (start, length, note, _vel) in enumerate(events):
            if i + 1 < len(events):
                length = min(length, events[i + 1][0] - start)
            if length < min_ms:
                continue
            a = int((start + 0.35 * length) * SR_IN / 1000)
            b = int((start + 0.9 * length) * SR_IN / 1000)
            seg = x[a:b]
            if len(seg) < 4096 or float(np.max(np.abs(seg))) < 1e-3:
                continue
            size = 1 << 20
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), size))
            want = 440.0 * 2 ** ((note - 69) / 12)
            lo, hi = int(want * 2 ** (-0.9 / 12) * size / SR_IN), int(want * 2 ** (0.9 / 12) * size / SR_IN) + 1
            k = lo + int(np.argmax(spec[lo:hi]))
            if spec[k] < 0.02 * spec.max():
                continue  # this note's own pitch is too weak in the sound to read
            errs.append(1200 * np.log2(k * SR_IN / size / want))
        if errs:
            out[track["name"]] = {"notes_measured": len(errs), "mean_cents": round(float(np.mean(errs)), 1),
                                  "worst_cents": round(float(max(errs, key=abs)), 1)}
    return out


def lint(piece):
    """Look a piece over before spending a render on it. Returns (errors, warnings, summary lines)."""
    errors, warnings, summary = [], [], []
    if not piece.get("tracks"):
        return ["the piece has no parts"], [], []
    end = max((s + l for t in piece["tracks"] for s, l, _n, _v in t["events"]), default=0)
    summary.append(f"{piece.get('title', piece['name'])}: {end / 1000:.1f} s of notes, {len(piece['tracks'])} parts")
    if end < 8000:
        warnings.append("under 8 seconds long")
    if end > 240000:
        warnings.append(f"{end / 1000:.0f} s long: each part takes about a fifth of that to render")
    if len(piece["tracks"]) > 10:
        warnings.append("more than 10 parts: the mix gets crowded and the render slow")
    names = [t["name"] for t in piece["tracks"]]
    if len(set(names)) != len(names):
        errors.append("two parts share a name")
    for t in piece["tracks"]:
        ev = sorted(t["events"])
        if not ev:
            errors.append(f"{t['name']}: no notes")
            continue
        pitches = [n for _s, _l, n, _v in ev]
        summary.append(f"  {t['name']:12s} {len(ev):4d} notes, MIDI {min(pitches)}-{max(pitches)}, "
                       f"from {ev[0][0] / 1000:.1f} s to {(ev[-1][0] + ev[-1][1]) / 1000:.1f} s, gain {t.get('gain_db', 0)} dB")
        if any(not 0 <= n <= 127 for n in pitches) or any(not 1 <= v <= 127 for *_x, v in ev):
            errors.append(f"{t['name']}: a note number or velocity is outside what MIDI allows")
        if any(s < 0 for s, *_x in ev):
            errors.append(f"{t['name']}: a note starts before zero")
        rng = t.get("range")
        if rng:
            out = [n for n in pitches if not rng[0] <= n <= rng[1]]
            if out:
                warnings.append(f"{t['name']}: {len(out)} of {len(ev)} notes lie outside the range this instrument was "
                                f"checked over ({rng[0]}-{rng[1]}), e.g. {sorted(set(out))[:4]}")
        cut = same = 0
        for (s1, l1, _n1, _v1), (s2, _l2, _n2, _v2) in zip(ev, ev[1:]):
            if s2 - s1 < 1.0:
                same += 1
            elif s2 - s1 < 0.5 * l1:
                cut += 1
        if same:
            errors.append(f"{t['name']}: {same} notes start together. A part is one voice, so only one would sound: "
                          "give each chord tone its own part")
        if cut:
            warnings.append(f"{t['name']}: {cut} notes are cut to under half their written length by the next note "
                            "(fine for a plucked run, wrong if they were meant to ring)")
        if t.get("gain_db", 0) > 6:
            warnings.append(f"{t['name']}: gain above +6 dB; the mix is levelled to the loudest moment anyway")
    return errors, warnings, summary


def _db(x):
    return float(10 * np.log10(np.mean(x ** 2) + 1e-12))


def loudness_curve(path, slices=16):
    """How loud the finished mix is through the piece: [(start seconds, dB)] for equal slices."""
    with wave.open(path, "rb") as w:
        sr = w.getframerate() * w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    chunks = np.array_split(x, slices)
    starts = np.cumsum([0] + [len(c) for c in chunks[:-1]]) / sr
    return [(round(float(t), 1), round(_db(c), 1)) for t, c in zip(starts, chunks)]


def part_levels(piece, takes, slices=8):
    """Each part's level in each slice of the piece, in dB as it sits in the mix before the final levelling.

    A part is levelled to its own loudest moment and then given its gain, so one loud note
    sets how quiet the rest of that part is. This table is where that shows: compare parts
    slice by slice, not by one figure for the whole piece. None means the part is silent there.
    """
    out = {}
    for track in piece["tracks"]:
        x = takes[track["name"]].astype(np.float64)
        peak = float(np.max(np.abs(x))) or 1.0
        x = x / peak * 10 ** (track.get("gain_db", 0) / 20)
        row = []
        for chunk in np.array_split(x, slices):
            level = _db(chunk)
            row.append(None if level < -70 else round(level))
        out[track["name"]] = row
    return out
