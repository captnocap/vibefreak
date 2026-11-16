"""Measures a recorded note: which sine waves it is made of and how they move.

Everything here is plain FFT arithmetic on a mono recording at 96 kHz, the
rate the instrument's converter runs at (other rates are resampled on load). The numbers
are chosen to answer the questions a person asks about a sound: how bright,
how hollow, how buzzy, how noisy, how much it wobbles, how fast it starts and
dies. `describe()` turns the numbers into those words using fixed thresholds
(listed in WORDS below), so the words can be traced back to a measurement.
"""
import wave

import numpy as np

SR = 96000
BANDS = [("sub", 20, 80), ("low", 80, 250), ("lowmid", 250, 800), ("mid", 800, 2500),
         ("high", 2500, 8000), ("air", 8000, 20000)]
N_HARM = 24
# 1/3-octave steps relative to the played pitch, from one octave below to ~6.5 octaves above.
REL_STEPS = np.arange(-3, 60)


def resample(x, rate):
    """Band-limited resampling to SR by resizing the spectrum."""
    if rate == SR or len(x) == 0:
        return x
    n_out = int(round(len(x) * SR / rate))
    spec = np.fft.rfft(x)
    out_bins = n_out // 2 + 1
    if out_bins <= len(spec):
        spec = spec[:out_bins]
    else:
        spec = np.concatenate([spec, np.zeros(out_bins - len(spec), dtype=complex)])
    return np.fft.irfft(spec, n_out) * (n_out / len(x))


def load(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: need 16-bit audio")
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return resample(data / 32768.0, rate)


def db(x, floor=-120.0):
    return float(max(floor, 20 * np.log10(max(x, 1e-12))))


def _spectrum(x):
    n = len(x)
    win = np.hanning(n)
    spec = np.fft.rfft(x * win)
    power = (np.abs(spec) ** 2) / (win.sum() ** 2) * 4  # a full-scale sine reads 1.0
    freqs = np.fft.rfftfreq(n, 1 / SR)
    return freqs, power


def _peak_near(freqs, power, target, tolerance):
    """Strongest bin within `tolerance` (a ratio, e.g. 0.03) of target; returns (freq, power incl. its skirts)."""
    df = freqs[1]
    lo = max(1, int((target * (1 - tolerance)) / df))
    hi = min(len(power) - 2, int(np.ceil((target * (1 + tolerance)) / df)))
    if hi <= lo:
        return target, 0.0
    k = lo + int(np.argmax(power[lo:hi + 1]))
    a, b = max(0, k - 2), min(len(power), k + 3)
    p = power[a:b].sum()  # a windowed sine spreads over a few bins; totals below are summed the same way
    # parabolic refinement of the peak position
    if 0 < k < len(power) - 1 and power[k] > 0:
        l, c, r = (np.log(max(v, 1e-30)) for v in power[k - 1:k + 2])
        denom = l - 2 * c + r
        shift = 0.5 * (l - r) / denom if denom != 0 else 0.0
    else:
        shift = 0.0
    return float((k + shift) * df), float(p)


def steady_window(x, start_ms=120, max_len=65536):
    """The stretch used for spectrum work: skips the attack, takes up to ~0.68 s."""
    start = int(start_ms * SR / 1000)
    seg = x[start:start + max_len]
    if len(seg) < 4096:
        seg = x[-max(len(x), 1):]
    n = 1 << int(np.floor(np.log2(max(len(seg), 2))))
    return seg[:n]


def spectrum_features(x, f0):
    """Spectrum of a steady stretch, described relative to the played pitch f0."""
    seg = steady_window(x)
    freqs, power = _spectrum(seg)
    audible = (freqs >= 20) & (freqs <= 20000)
    total = float(power[audible].sum())
    out = {"level_db": db(np.sqrt(np.mean(seg ** 2)))}
    if total < 1e-10:
        out["silent"] = True
        return out

    # refine the pitch from whichever of the first four harmonics is strongest
    best = max(range(1, 5), key=lambda k: _peak_near(freqs, power, f0 * k, 0.04)[1])
    measured, _ = _peak_near(freqs, power, f0 * best, 0.04)
    f0m = measured / best
    out["f0_hz"] = round(f0m, 2)
    out["cents_off"] = round(1200 * np.log2(f0m / f0), 1)

    harm = []
    harm_power = 0.0
    for k in range(1, int(20000 // f0m) + 1):
        _, p = _peak_near(freqs, power, f0m * k, min(0.03, 0.4 / k))
        harm_power += p
        if k <= N_HARM:
            harm.append(p)
    harm = np.array(harm)
    ref = harm.max() if harm.max() > 0 else 1.0
    out["harmonics_db"] = [round(db(np.sqrt(h / ref), -90), 1) for h in harm]
    out["harmonic_share"] = round(min(1.0, harm_power / total), 4)
    out["fundamental_share"] = round(float(harm[0] / total), 4)
    odd, even = harm[0::2].sum(), harm[1::2].sum()
    out["odd_even_db"] = round(10 * np.log10(max(odd, 1e-15) / max(even, 1e-15)), 1)

    f, p = freqs[audible], power[audible]
    centroid = float((f * p).sum() / p.sum())
    out["centroid_hz"] = round(centroid, 1)
    out["centroid_harm"] = round(centroid / f0m, 2)  # brightness in "which harmonic is the centre of mass"
    cum = np.cumsum(p) / p.sum()
    out["rolloff85_hz"] = round(float(f[np.searchsorted(cum, 0.85)]), 1)
    out["flatness"] = round(float(np.exp(np.mean(np.log(p + 1e-20))) / (np.mean(p) + 1e-20)), 5)
    out["below_f0_share"] = round(float(power[(freqs >= 20) & (freqs < f0m * 0.75)].sum() / total), 4)
    out["bands_db"] = {name: round(10 * np.log10(max(power[(freqs >= lo) & (freqs < hi)].sum(), 1e-15) / total), 1)
                       for name, lo, hi in BANDS}

    # 1/3-octave profile relative to the pitch: the shape used to compare two sounds
    edges = f0m * 2.0 ** ((REL_STEPS - 0.5) / 3)
    prof = []
    for lo, hi in zip(edges, np.append(edges[1:], edges[-1] * 2 ** (1 / 3))):
        sel = (freqs >= lo) & (freqs < min(hi, 20000))
        prof.append(round(10 * np.log10(max(power[sel].sum(), 1e-15) / total), 1) if sel.any() and lo < 20000 else -150.0)
    out["profile_db"] = prof

    # strongest individual sine waves, as ratios to the pitch (shows inharmonic partials)
    peaks = []
    work = power.copy()
    work[~audible] = 0
    for _ in range(10):
        k = int(np.argmax(work))
        if work[k] <= 0:
            break
        fpk, ppk = _peak_near(freqs, power, freqs[k], 0.002)
        level = db(np.sqrt(ppk / ref), -90)
        if level < -50:
            break
        peaks.append([round(fpk / f0m, 3), round(level, 1)])
        w = max(3, int(0.02 * k))
        work[max(0, k - w):k + w + 1] = 0
    out["peaks"] = sorted(peaks)
    return out


def movement_features(x, f0, start_ms=120):
    """How much the sound changes while a note is held: beating, wobble, drift."""
    seg = x[int(start_ms * SR / 1000):]
    out = {}
    if len(seg) < 16384:
        return out
    # loudness measured over a whole number of cycles, so a steady wave reads as flat
    span = max(1, int(round(4 * SR / f0)))
    power = np.convolve(seg ** 2, np.ones(span) / span, mode="valid")
    hop = SR // 200  # 5 ms
    env = np.sqrt(power[::hop])
    frames = len(env)
    mean = env.mean()
    if mean < 1e-6 or frames < 16:
        return out
    out["am_depth"] = round(float(env.std() / mean), 3)
    e = (env - mean) * np.hanning(frames)
    es = np.abs(np.fft.rfft(e))
    ef = np.fft.rfftfreq(frames, hop / SR)
    sel = (ef >= 0.7) & (ef <= 25)
    if out["am_depth"] > 0.02 and sel.any() and es[sel].max() > 0:
        out["am_rate_hz"] = round(float(ef[sel][np.argmax(es[sel])]), 2)
    size, step = 8192, 4096
    cents = []
    win = np.hanning(size)
    freqs = np.fft.rfftfreq(size, 1 / SR)
    for i in range(0, len(seg) - size, step):
        p = np.abs(np.fft.rfft(seg[i:i + size] * win)) ** 2
        p[freqs < 20] = 0
        if p.sum() > 0:
            cents.append((freqs * p).sum() / p.sum())
    if len(cents) >= 3:
        cents = np.array(cents)
        out["centroid_wobble"] = round(float(cents.std() / cents.mean()), 3)
        out["centroid_drift"] = round(float((cents[-1] - cents[0]) / cents.mean()), 3)
    return out


def envelope_features(x, hold_ms, f0=None, oscillator_only=False):
    """Loudness over time: how fast the note starts, where it settles, how it ends.

    With oscillator_only (a recording taken before the amplifier) there is no attack or
    release to speak of, so only "does it die away while the key is held" is reported.
    """
    hop = SR // 500  # 2 ms
    frames = len(x) // hop
    if frames < 10:
        return {}
    env = np.sqrt(np.mean(x[:frames * hop].reshape(frames, hop) ** 2, axis=1))
    # smooth over at least two cycles of the note so its own waveform does not read as an envelope
    k = 5 if not f0 else max(5, int(np.ceil(2 * 500 / f0)))
    env = np.convolve(env, np.ones(k) / k, mode="same")
    peak = float(env.max())
    if peak < 1e-5:
        return {"silent": True}
    t = np.arange(frames) * hop * 1000 / SR
    out = {"peak_db": db(peak)}
    held = env[t < hold_ms]
    if len(held) >= 30:
        third = len(held) // 3
        first, last = np.sqrt(np.mean(held[:third] ** 2)), np.sqrt(np.mean(held[-third:] ** 2))
        # level in the last third of the held note against the first third: beating averages out, a pluck does not
        out["sustain_ratio"] = round(float(last / first), 3) if first > 0 else None
        ipk = int(np.argmax(held))
        if out["sustain_ratio"] is not None and out["sustain_ratio"] < 0.7:
            after = np.nonzero(held[ipk:] <= 0.5 * held.max())[0]
            if len(after):
                out["decay_half_ms"] = round(float(t[ipk + after[0]] - t[ipk]), 1)
        if not oscillator_only:
            above10 = np.nonzero(held >= 0.1 * held.max())[0]
            above90 = np.nonzero(held >= 0.9 * held.max())[0]
            if len(above10) and len(above90):
                out["attack_ms"] = round(float(t[above90[0]] - t[above10[0]]), 1)
            out["peak_at_ms"] = round(float(t[ipk]), 1)
    rel = env[t >= hold_ms]
    if not oscillator_only and len(rel) > 5 and rel[0] > 1e-5:
        below = np.nonzero(rel <= rel[0] * 0.1)[0]
        out["release_ms"] = round(float(below[0] * hop * 1000 / SR), 1) if len(below) else None
    return out


# word -> (feature, comparison, threshold). describe() applies these in order.
WORDS = [
    ("very dark", "centroid_harm", "<", 1.2),
    ("dark", "centroid_harm", "<", 1.8),
    ("bright", "centroid_harm", ">", 3.0),
    ("very bright", "centroid_harm", ">", 6.0),
    ("pure (near sine)", "fundamental_share", ">", 0.93),
    ("hollow (odd harmonics)", "odd_even_db", ">", 12.0),
    ("octave-ish (even harmonics lead)", "odd_even_db", "<", -6.0),
    ("weak fundamental", "fundamental_share", "<", 0.08),
    ("sub weight below the note", "below_f0_share", ">", 0.15),
    ("noisy", "harmonic_share", "<", 0.6),
    ("mostly noise or inharmonic", "harmonic_share", "<", 0.25),
    ("beating / thick", "am_depth", ">", 0.12),
    ("timbre moves while held", "centroid_wobble", ">", 0.08),
    ("plucked (dies while held)", "sustain_ratio", "<", 0.35),
    ("slow attack", "attack_ms", ">", 80.0),
]


def describe(features):
    words = []
    for word, key, op, limit in WORDS:
        v = features.get(key)
        if v is None:
            continue
        if (op == "<" and v < limit) or (op == ">" and v > limit):
            words.append(word)
    drop = set()
    if "very dark" in words:
        drop.add("dark")
    if "very bright" in words:
        drop.add("bright")
    if "mostly noise or inharmonic" in words:
        drop.add("noisy")
    return [w for w in words if w not in drop]


def analyze(x, f0, hold_ms=None, oscillator_only=False):
    """All measurements of one recorded note. `x` is float samples, f0 the played pitch in Hz."""
    if hold_ms is None:
        hold_ms = len(x) * 1000 / SR
    held = x[:int(hold_ms * SR / 1000)]
    out = spectrum_features(held, f0)
    out.update(movement_features(held, out.get("f0_hz", f0)))
    out.update(envelope_features(x, hold_ms, f0, oscillator_only))
    out["words"] = describe(out)
    return out


def analyze_file(path, f0, hold_ms=None, oscillator_only=False):
    return analyze(load(path), f0, hold_ms, oscillator_only)


def profile_distance(a, b):
    """How different two sounds' spectra are, pitch aside: RMS dB gap over the 1/3-octave profile.

    Only bands that matter in at least one of the two (above -60 dB) count.
    """
    pa, pb = np.array(a["profile_db"]), np.array(b["profile_db"])
    sel = (pa > -60) | (pb > -60)
    if not sel.any():
        return 0.0
    d = np.clip(pa[sel], -60, 0) - np.clip(pb[sel], -60, 0)
    return float(np.sqrt(np.mean(d ** 2)))


def summary(f):
    """One line a person can read."""
    if f.get("silent"):
        return "silent"
    h = f.get("harmonics_db", [])
    first = " ".join(f"{v:.0f}" for v in h[:8])
    return (f"{', '.join(f.get('words', [])) or 'plain'} | centre of brightness at harmonic {f.get('centroid_harm')}"
            f" ({f.get('centroid_hz')} Hz) | harmonics 1-8 dB: {first} | harmonic share {f.get('harmonic_share')}"
            f" | odd/even {f.get('odd_even_db')} dB")
