# The lab: measuring what the MicroFreak does

VibeFreak runs Arturia's MicroFreak firmware in an emulator. The lab is a layer on top that makes it usable
as a measuring instrument: put a patch on it, play a note, get a recording and numbers, and keep the numbers
in a knowledge base that maps "what sound do I want" to "what do I set on the panel".

Nothing here contains Arturia's firmware. You supply the firmware update file yourself
(`~/.config/vibefreak/firmware.mff`, version 5.0.0.2084 is what everything was measured on).

## Pieces

| Piece | What it is |
|---|---|
| `crates/vibefreak-lab` | The emulator behind a pipe: one JSON command per line in, one JSON reply per line out. Emulated time only moves when a command asks, so runs repeat exactly. |
| `lab/freaklab/client.py` | Python wrapper for that pipe. |
| `lab/freaklab/params.py` | Where the firmware keeps the live patch in memory, so every setting can be read back. |
| `lab/freaklab/ocr.py` | Reads the text off the emulated 128x64 display. |
| `lab/freaklab/patch.py` | A patch in panel terms (knob percentages, button states): apply, read back, play. |
| `lab/freaklab/matrix.py` | The modulation matrix and the Assign buttons, driven through the Matrix encoder and checked against firmware memory. |
| `lab/freaklab/menu.py` | Utility > Preset > Modulations (LFO Retrig, Press Mode, Key/Arp Mode), walked by reading the menu off the screen. |
| `lab/freaklab/analyze.py` | The measurements: harmonics, brightness, noise, movement, envelope. |
| `lab/freaklab/sweep.py`, `modsweep.py`, `calibrate.py` | The measurement runs that fill `lab/kb/`. |
| `lab/freaklab/kb.py` | Search the knowledge base; write `kb/GUIDE.md`. |
| `lab/freak` | Command line for all of it (`lab/freak --help`). |
| `lab/listen.py`, `lab/web/listen.html` | The listening page: every render in `lab/out/` playable in a browser, with its panel settings and harmonics. Runs as the user service `vibefreak-listen` on port 8770 (`lab/deploy/vibefreak-listen.service`); home network and VPN ranges only, read-only, no login. |
| `lab/kb/` | The knowledge base: one JSON per oscillator type, the filter, the envelope, modulation, the panel calibration, and the generated `GUIDE.md`. |

Needs Python 3 with numpy and Pillow, and the release build of `vibefreak-lab`
(`cargo build --release -p vibefreak-lab`).

## How settings get in and out

- Knobs are set with MIDI control changes, which the firmware treats as absolute positions (128 steps).
  The emulated pots are not used for that: with this firmware's pot handling a single jump of a pot is mostly
  ignored, only gradual movement registers.
- Buttons (filter type, amp mod, cycling-envelope mode, paraphonic) are clicked until the firmware reports
  the wanted state.
- After applying, the patch is read back from the firmware's memory, and the Wave/Timbre/Shape texts are read
  from the display, so recordings are labelled with what the firmware held, not with what was requested.

## Two recordings per note

`render` taps the signal twice: as the firmware wrote it to the converter (the digital oscillator, exact),
and after the emulator's model of the analog filter and amplifier. It also returns the control signals the
firmware sends to the analog board (cutoff, resonance, amplifier level) block by block, which is where the
envelope timings in the knowledge base come from.

## Three corrections this fork makes to the emulator

1. **The audio is 96 kHz, not 48 kHz.** The firmware sets the converter's dual-rate bits (TLV320AIC3104
   register 7 = 0x6A); read as 48 kHz every note is exactly an octave flat; and the attack times the firmware
   prints on its display match the envelope it outputs only at 96 kHz. The sample-rate constant, the CPU time
   per audio block and the live audio output were changed to match.
2. **The filter's cutoff scale** now follows the frequencies the firmware displays (16 Hz to 26.8 kHz,
   10.71 octaves) instead of an assumed 20 Hz to 20.48 kHz.
3. Measurement taps: the pre-filter block and the model's current cutoff and resonance are readable.

## Limits

See the "How much to trust each part" section of `kb/GUIDE.md`. In short: oscillators exact, envelope timing
exact, envelope timing exact, modulation (matrix depths, LFO, cycling envelope) exact, filter a model;
sample-based types, the vocoder, arpeggiator patterns, the sequencer and paraphonic mode not measured.

Tempo after fix 1 was checked two ways (`kb/modulation.json`): a synced LFO at 1/4 takes one beat of the
tempo on the screen within 0.1 % at five tempos from 30 to 240 BPM, and the arpeggiator plays exactly two
notes per beat at the same five.

Two things about the emulator to know when scripting modulation:

- Once a matrix point modulates a knob, the firmware's parameter table holds the moving value, not the knob
  position. `freak play` reads the patch back before it sets the matrix for that reason.
- A freshly started emulator shows Key/Arp Mode as Linear but hands out a random value per note until the
  setting has been changed once. `patch.apply` sets it (Random, then Linear) whenever a Key/Arp point is used.

## Lab protocol (for scripting without Python)

Start `target/release/vibefreak-lab [firmware.mff]`; it prints a ready line, then answers these, one JSON
object per line:

`step {ms}` · `midi {bytes}` · `key {key, pressure}` · `pot {name, value 0..4095}` · `enc {name, delta}` ·
`sw {name, pressed}` · `click {name}` · `filter_mode {mode}` · `touch {value, touched}` ·
`render {ms, wav?, raw_wav?, cv_every?}` · `cv` · `oled` · `leds` · `codec` · `mem {addr, len}` · `swd {cmd}` ·
`save_qspi {path}` · `time` · `quit`
