---
name: microfreak-compose
description: Compose and render a short original piece of music on the emulated MicroFreak from a mood, theme, image, scene or title, and put it on the listening page. Use whenever the request is for music rather than a single sound, e.g. "/microfreak-compose a lighthouse in fog", "write me something triumphant", "make a piece about the ocean", "compose a track that feels like a heist", "demo a spooky mood on the microfreak", or any bare mood or theme given right after this skill is loaded. For one sound or patch ("a hollow bass"), use microfreak-sound instead.
---

# Composing a piece from a mood or theme

The prompt is a mood, a theme, an image or a title, sometimes only a word or two. Your job is to write a
short original piece that *demonstrates* it, render it on the emulated MicroFreak, and hand over a link
the person can press play on. They own the real instrument; every part's panel settings are shown beside
the piece, so anything they like they can dial in.

Work in the repo, usually `~/code/vibefreak`. Everything below runs from its root.

## What makes one of these good

A mood is not a preset. "Sad" could be slow D minor with a pad, and so could a thousand other requests.
The pieces here that work each have **one idea carried all the way through**, an idea you could explain
to someone in two sentences and they could then hear:

- `claudes_sonnet`: a sonnet's form with the words removed. Fourteen lines of five short-long feet,
  rhymes as matching line endings, the turn at line nine.
- `one_sixteenth_early` (prompt: "a heist that starts going wrong"): three players share one tune and
  never move on the same sixteenth; then one comes in a sixteenth early, and keeps getting earlier.
- `window_seat_3am` (prompt: "3am rain on a bus window"): street lamps pass at exactly even intervals
  and the drops never do; when a running drop meets a hanging one, two bells strike the same note.

Skim one of those files in `lab/pieces/` to see how an idea becomes notes. Do not reuse their ideas.

So, before any notes:

1. **Say what the prompt means to you in a sentence**, concretely: a place, a moment, who is there, what
   is about to happen or not happen. An abstract word ("melancholy", "tension") is where you start, not
   where you stop.
2. **Find the one idea** that turns that into music. A process, a picture, a form, a constraint, a rule
   that gets broken once. If the prompt is a thing with structure of its own (a poem form, a journey, a
   machine, a game, a season), borrow that structure.
3. **Then choose the levers** below so that they serve the idea. State your choices in the reply, because
   the reasoning is half of what the person wants to see.

### The levers

| Lever | What it does |
|---|---|
| Tempo and pulse | Under 70 BPM floats or mourns; 90-120 walks or works; above 130 runs. No steady pulse at all reads as space or dread. Swing loosens, straight sixteenths tighten. |
| Mode and harmony | major: open, settled. lydian: wonder. mixolydian: easy, sunlit. dorian: wistful but moving. minor: grave. phrygian or locrian: threat. whole_tone: weightless, dreamlike. Slow chord changes are calm; unresolved ones keep tension; a late change of key is an event. |
| Register | High and thin is fragile or cold. Low is weight. A wide gap between bass and tune is loneliness. |
| Density | How many parts, and how many notes a bar. Silence is a tool: rests make the next note matter. |
| Timbre | Which instruments (see below), how dark or bright, how fast notes start. Slow attacks blur; plucks and bells mark time. |
| Movement | Vibrato, filter wobble, a filter that opens over a section. Stillness is also a choice. |
| Shape over time | What changes between the first half-minute and the last. Every piece needs at least one thing that arrives, leaves or turns. |

## Instruments

```
lab/freak instruments                     the measured instruments: name, role, note range, what each sounds like
lab/freak instruments --check NAME ...    play stock ones again and measure (tuning, brightness, loudness over time)
```

Pick from these first: they are known to be in tune and to behave as described. Change any field to suit:

```python
p.part("lead", "voice", cutoff=50, attack=25)                      # plain fields by keyword
p.part("pad", "pad_wide", lfo_rate=42, **{"lfo>cutoff": 5})        # matrix points need a dict
```

The fields are the ones `lab/freak --help` lists. `lab/kb/GUIDE.md` has what the numbers mean: the
"Envelope" section for attack and decay times (attack 62 is about a second), and "Modulation matrix, LFO
and cycling envelope" for depths (25 on Pitch is an octave, 1 is about half a semitone, 10 on Cutoff is
about an octave). To hear a changed or home-made patch on its own before a piece relies on it, use
`lab/freak play ... --name _try`: a name starting with an underscore stays off the listening page. The
`microfreak-sound` skill is the way to design a patch from scratch.

Things that waste a render if forgotten:

- **A part is one voice.** The instrument is monophonic, and a piece is made the way you would multitrack
  it: one take per part. A three-note chord is three parts, each holding one chord tone. Two notes that
  start together in one part is an error.
- **Stay inside each instrument's range** unless you have checked beyond it. Some thin out or go quiet
  higher up.
- **Velocity is loudness, on every instrument**: roughly 6 dB between 45 and 110, 3 to 4 dB between 64
  and 96 (on `voice` and `string` it also brightens). Each part is levelled to its own loudest note
  before its `gain_db` is applied, so a single hard note makes the rest of that part sit lower. Write
  dynamics with velocity; set the balance between parts with `gain_db`.
- **The Dec/Rel knob is both decay and release.** A note keeps ringing after it is let go for about as
  long as its decay, whatever length you wrote. For short, detached notes lower `decay` (10 to 20), not
  just `hold`.
- **Drums are parts too**: `kick` (play MIDI 36), `snare` and `hat` (any note in their range; the note
  barely matters). The hit is the envelope, so any written length of a step or so is fine.
- Do not use the Sample, grain, Vocoder or Chords oscillator types: they are unmeasured or do not play the
  note you ask for.
- 3 to 7 parts is the comfortable size. Every extra part is another full take to render.

## Writing the score

A piece is a Python file `lab/pieces/<slug>.py` with a `build()` function. The slug is lowercase letters,
digits and underscores, and must equal the `name` given to `Piece`. Use the helpers in
`lab/freaklab/compose.py` (short; read its docstrings). This shows the calls, not a piece worth copying:

```python
"""Title: a paragraph on the idea, as the module docstring."""
from freaklab.compose import Piece, chord, chord_notes, nearest, note, scale

def build():
    p = Piece("my_slug", "My Title", bpm=96, steps_per_beat=4, reverb_db=-17,
              about="One or two sentences for the listening page: what it is and the idea behind it.")
    tune = p.part("tune", "reed", role="what this part is doing, in words", gain_db=0, pan=0.0)
    low = p.part("pad_low", "pad_warm", role="root of each chord", gain_db=-7, pan=-0.5, attack=40)
    bass = p.part("bass", "bass_hollow", role="...", gain_db=-5)

    BAR = 16                                    # steps: sixteenths in 4/4
    for bar, name in enumerate(["Am", "F", "C", "G"] * 4):
        root = chord(name)[0]                   # pitch class of the root
        low.play(bar * BAR, BAR - 0.5, nearest(root, 48), 80)          # one note: step, steps, pitch, velocity
        bass.play(bar * BAR, BAR - 1, nearest(root, 33), 92)
    end = tune.line(0, ["E4", None, "A4", "G4"], [4, 2, 2, 8],         # a run; None is a rest
                    velocity=[100, 0, 70, 90], hold=0.9)               # returns the step after it
    p.mark(0, "the tune alone")                 # structure lines, stamped with the right time for you
    p.mark(8 * BAR, "the bass joins")
    p.tempo(15 * BAR, 16 * BAR, 1.0, 1.4)       # these steps slow down; afterwards back to normal
    return p.build()
```

- Time is counted in steps: a sixteenth when `steps_per_beat=4`; use 3 for triplet feels. Steps can be
  fractions.
- Pitches are names (`"C4"` is MIDI 60, `"Bb2"`, `"F#5"`) or numbers. `chord("Dm7")` gives pitch classes,
  `nearest(pc, low)` places one in the octave starting at `low`, `chord_notes("Dm", 50)` spells a chord
  upward, `scale("D", "dorian", 60)` a scale.
- `p.tempo(a, b, start, end)` bends only steps a to b. `p.tempo(a, start=0.8)` changes tempo from step a
  to the end (0.8 is 25 % faster). `p.set_swing(0.33)` shuffles.
- `p.mark(step, text)` builds the structure list the page shows; `p.clock(step)` gives the m:ss of a step
  if you need it elsewhere. Write marks as what happens, in plain words.
- `p.humanize(ms=8, velocity=6)` loosens machine timing (notes on the same step stay together). It also
  blurs written accents: pass `velocity=0` to keep them, `parts=[...]` to loosen only some parts. Leave it
  out when exactness is the point.
- `reverb_db` is added in the mix and is not the synth: -17 is a modest room, -12 vast or distant, -24 or
  `None` close and dry.

Write the notes on purpose. A generated arpeggio under a held pad is what everyone reaches for; ask
whether the idea is audible in the notes themselves. Use loops for the mechanical parts and write the
parts that carry the idea by hand.

Aim for 45 to 100 seconds unless asked otherwise: long enough to have a shape, short enough to be heard
in one go. Leave the ending room to ring (`tail_ms`, default 3000).

Keep it original. If the theme names an existing song, artist, film or game, write something in that
spirit with your own melody and harmony, not a version of their tune.

## Check, render, read the report

```
lab/freak piece <slug> --check   length, notes per part, ranges, mistakes, the structure lines; instant
lab/freak piece <slug>           render every part, mix, report, and put it on the listening page
```

A 90-second piece with six parts renders in about 40 seconds. You cannot hear the result, so the report
is your ears. Read all of it, and say plainly in your reply that the piece was checked by measurement
and not heard.

- **`--check`** says "no warnings", or each warning is something you intended.
- **Tuning**: held notes within about 10 cents; pads and vibrato parts read looser, up to about 20,
  because they are detuned or moving on purpose. Drums and noise are not listed. "No note long enough to
  measure" is not a failure.
- **Loudness of the mix through the piece** (sixteen slices): does it follow the shape you meant? If a
  section is supposed to build, drop away or stop, find it in the numbers. A flat line means the
  arrangement is not changing as much as you think.
- **Each part's level in eighths of the piece**: this is the balance check. Read down a column: in that
  stretch, which part is on top, and is that the one you want heard? A tune 6 dB or more under the bass
  is buried; a part more than about 25 dB under everything else is probably inaudible while they play.
  Sparse parts (a hat, a single drop) read low on average and can still be clear when they are alone.
- **Balance** is `gain_db` per part. A workable start: the tune 0, bass -5, each pad voice -7, bells and
  plucks -7 to -9, kick -4, snare -9, hat -14 inside a groove (nearer -8 if it has to be heard alone),
  wind and other noise -8 to -12. Spread parts with `pan` (-1 left to 1 right); keep bass, kick and the
  tune near the middle.

One or two rounds of adjusting is normal. Do not polish past what the measurements can tell you; the
person's ears are the next check, and re-rendering after their feedback is cheap.

## Handing it over

Reply with:

- the title and the link `http://rack.local:8770/#<slug>` (over the VPN: `http://10.0.0.4:8770/#<slug>`)
- what you took the prompt to mean and the one idea, in two or three sentences
- the choices that follow from it (tempo, mode, instruments, the shape), briefly
- that it was checked by measurement and not by ear, and an invitation to say what sounds off

Then commit the new file in `lab/pieces/` to `main` with a one-line message (the recordings in `lab/out/`
are not tracked). Do not push.

If the service behind the page is down, the WAV is still at `lab/out/<slug>.wav`.
