---
name: microfreak-sound
description: Design, audition and explain Arturia MicroFreak sounds using the emulator lab in this repo. Use when asked for MicroFreak settings for a described sound ("a hollow bass", "glassy bell", "make it darker"), to match a recording on the MicroFreak, to explain what a MicroFreak oscillator type or knob does, or to measure a patch.
---

# MicroFreak sound design with the lab

The repo is a fork of the VibeFreak emulator, which runs Arturia's real MicroFreak firmware. `lab/` adds a
way to set a patch, play it, record it and measure it, plus a knowledge base built from those measurements.
The person asking owns the hardware: the goal is settings they can dial in on the real panel and a sound that
matches what was measured here.

## Read first

- `lab/kb/GUIDE.md`: what every measured oscillator type does, knob by knob, what the screen reads at each
  knob position, envelope times, and how far to trust each part. Read the introduction and the sections for
  the oscillator types you are considering; it is long, so do not read all of it for one request.
- `lab/README.md`: how the lab works and its limits.

## Tools (run from the repo root; if you are elsewhere, the checkout is usually `~/code/vibefreak`)

```
lab/freak engines                               oscillator types and their three knob names
lab/freak find --word hollow --where "centroid_harm<3" --engine V.Analog --sort fundamental_share
lab/freak play engine=SawX wave=30 timbre=70 shape=0 cutoff=55 resonance=20 --note C2 --name idea1
lab/freak play engine=V.Analog cutoff=45 lfo:cutoff=10 lfo_shape=tri lfo_rate=60 env:pitch=-2 key_arp:cutoff=100
lab/freak play engine=Harmo assign1=resonance cyc_env:assign1=30 cyc_mode=loop cyc_amount=100 cyc_rise=30
lab/freak analyze some.wav --note C3            measure any 16-bit WAV
lab/freak match some.wav --note C3              closest measured oscillator settings to a recording
lab/freak knob cutoff 60                        what the screen reads at a knob position
lab/freak selftest                              run this if anything behaves oddly
```

`freak play` starts from a plain patch (open filter, organ envelope) every time, applies the fields given,
and prints an "On the panel" block in the instrument's own wording, then measurements of the oscillator alone
and of the full output. WAVs land in `lab/out/` (96 kHz mono).

Modulation is part of the patch: a matrix point is `SOURCE:DEST=AMOUNT` (-100..100; sources `cyc_env env lfo
pressure key_arp`, destinations `pitch wave timbre cutoff assign1 assign2 assign3`), an Assign column is
pointed with `assign1=resonance`, and the LFO with `lfo_shape`, `lfo_rate` (or `lfo_sync=on lfo_div=1/8`).
The scales are in the guide's "Modulation matrix, LFO and cycling envelope" section: amount 25 on Pitch is
one octave, 100 on Cutoff is the whole range, and on anything else the amount is percent of that knob's
travel. A CycEnv point does nothing until `cyc_amount` is above zero. A modulated patch takes a few seconds
longer to set up because the matrix is driven through the encoder like a hand would. If the binary is missing:
`~/.cargo/bin/cargo build --release -p vibefreak-lab`. The firmware file must be at
`~/.config/vibefreak/firmware.mff`.

## Working method

1. Turn the request into measures (the guide's "Turning a request into settings" section has the mapping).
   Say which measures you are aiming for, in plain words.
2. Pick one or two oscillator types from the guide, then use `freak find` to land on a starting setting.
3. Render with `freak play`, read the numbers, adjust one thing at a time. Three to six renders is normal.
   Check more than one note if the sound will be played across the keyboard.
4. Answer with: the "On the panel" block, one or two sentences on why those settings give that sound, and the
   path of the WAV so the person can listen before touching the hardware.

## Honesty rules

- The oscillator is exact; the filter is a model. When a sound depends on resonance, self-oscillation or
  filter drive, say that the real filter will differ and that the knob position is a starting point.
- Not measured, so do not present numbers for them: Sample and the three grain types, the Vocoder, the
  arpeggiator/sequencer, paraphonic mode, cycling-envelope Rise/Fall shapes, and how the real touch keyboard's
  pressure feels. You can still describe from general knowledge, labelled as such.
- The spectrum measures describe a steady note. With an LFO or envelope moving the tone, read
  `centroid_wobble`, `am_depth` and `am_rate_hz` for the movement, and say that the other figures are an
  average over it.
- A word like "bright" in the tool output is a threshold on a measurement, not a judgment. If the request is
  subjective ("warmer"), state the direction you moved and by how much.
- If the emulator and the hardware disagree for the person, that is useful: note it in `lab/kb/field-notes.md`
  with the patch and what differed.
