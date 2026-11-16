"""One Sixteenth Early: a heist that starts going wrong.

The plan is a hocket. Three players (bass, plucked string, electric piano) share one
two-bar figure in D dorian, and the plan's only rule is that no two of them ever move
on the same sixteenth: each has its own slots, and the tune exists only while everyone
keeps to them. A hi-hat ticks the beat like a synchronised watch and never changes its
mind about where the beat is.

The figure is taught one player at a time, then moved up a fourth (inside the building),
then brought back. On its fifth time through, the piano plays its high note one
sixteenth early and a semitone flat: E flat instead of E. Everyone freezes; the watch
keeps ticking; a pad picks the wrong note up and holds it.

They carry on, but the mistake is now in the loop. The piano's bar is fifteen steps
long instead of sixteen, so each bar it arrives one more sixteenth early and lands on
the others' slots. The wrongness spreads the way a wrong note would: A becomes A flat
in the bass, B becomes B flat, the plucks double up. An alarm bell starts on the
piano's own mistake (A to E flat, a tritone, two octaves up), the tempo pushes, and
the piano's loop keeps shrinking until it is nothing but A, E flat, A, E flat.

It does not end. Everything cuts out where a downbeat should be, and what is left is
the alarm and the watch, at the tempo the plan was written in.

Times are counted in sixteenths; a bar is 16 steps. Nothing is humanized: the plan is
exact on purpose, and everything that sounds late or early was written that way.
"""
from freaklab.compose import Piece, note

BAR = 16

# The plan, bar A and bar B of the two-bar figure: (step in the bar, steps long, pitch, velocity).
BASS_A = [(0, 3, "D2", 100), (6, 2, "A2", 84), (12, 2, "C3", 88)]
BASS_B = [(0, 3, "D2", 100), (6, 2, "A2", 84), (12, 1.5, "G2", 84), (14, 1.5, "A2", 92)]
STRING_A = [(2, 1, "D3", 84), (8, 2, "F3", 88), (11, 1, "G3", 80), (15, 1, "A3", 92)]
STRING_B = [(2, 1, "D3", 84), (8, 2, "F3", 88), (13, 2, "B3", 96)]
KEYS_A = [(3, 1, "A3", 78), (5, 3, "D4", 100), (10, 2, "C4", 86), (14, 2, "B3", 82)]
KEYS_B = [(3, 1, "A3", 78), (5, 3, "E4", 104), (10, 4, "D4", 90)]

# After the slip. The piano keeps its mistake; later the others catch it.
KEYS_B_WRONG = [(3, 1, "A3", 84), (5, 3, "Eb4", 112), (10, 4, "D4", 92)]
KEYS_A_FLAT = [(3, 1, "A3", 88), (5, 3, "D4", 104), (10, 2, "C4", 92), (14, 2, "Bb3", 96)]
BASS_A_SHAKEN = [(0, 3, "D2", 108), (6, 2, "Ab2", 96), (10, 1, "D2", 80), (12, 2, "C3", 92)]
BASS_B_SHAKEN = [(0, 3, "D2", 108), (6, 2, "Ab2", 96), (10, 1, "D2", 80), (12, 1.5, "G2", 88), (14, 1.5, "Ab2", 100)]
STRING_A_SHAKEN = [(2, 1, "D3", 96), (3, 1, "D3", 70), (8, 1, "F3", 98), (9, 1, "F3", 72),
                   (11, 1, "G3", 92), (12, 1, "G3", 70), (15, 1, "Ab3", 104)]
STRING_B_SHAKEN = [(2, 1, "D3", 96), (3, 1, "D3", 70), (8, 1, "F3", 98), (9, 1, "F3", 72),
                   (13, 1, "B3", 104), (14, 1, "Bb3", 100)]

# Running. The bass gives up its slots for straight eighths; the string scrambles up and falls down a
# diminished chord (D F Ab B) in sixteenths.
BASS_RUN = [
    "D2 D2 F2 D2 Ab2 D2 Eb2 D2",
    "D2 D2 F2 D2 Ab2 G2 F2 Eb2",
    "D2 D2 F2 D2 Ab2 D2 Eb2 D2",
    "D2 F2 Ab2 C3 Eb3 C3 Ab2 F2",
    "D2 D2 Eb2 Eb2 F2 F2 Ab2 Ab2",
    "A2 A2 Bb2 Bb2 C3 C3 Eb3 Eb3",
]
STRING_RUN_UP = [(2, 1, "D3", 104), (3, 1, "F3", 96), (4, 1, "G3", 100), (5, 1, "Ab3", 112),
                 (10, 1, "D3", 104), (11, 1, "F3", 96), (12, 1, "G3", 100), (13, 1, "Ab3", 108), (14, 1.5, "B3", 118)]
STRING_RUN_DOWN = [(1, 1, "D4", 118), (2, 1, "B3", 100), (3, 1, "Ab3", 96), (4, 1, "F3", 104),
                   (9, 1, "D4", 118), (10, 1, "B3", 100), (11, 1, "Ab3", 96), (12, 1, "F3", 104), (14, 1.5, "D3", 112)]

# How many steps the piano waits between one "A, E flat" and the next, once that is all it has left.
PANIC = [8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3]   # and then 2 until the end: a trill


def lay(part, bar, cells, up=0, early=0):
    """Put one bar of cells into a part: `up` semitones higher, `early` steps ahead of where the bar is."""
    for slot, steps, pitch, velocity in cells:
        part.play(bar * BAR + slot - early, steps, note(pitch) + up, velocity)


def build():
    # the plan's rule, checked: in the written figure no two players start a note on the same step
    for bar in ((BASS_A, STRING_A, KEYS_A), (BASS_B, STRING_B, KEYS_B)):
        slots = [cell[0] for cells in bar for cell in cells]
        assert len(slots) == len(set(slots)), "two players share a slot in the plan"

    p = Piece("one_sixteenth_early", "One Sixteenth Early", bpm=104, steps_per_beat=4,
              about=("A heist that starts going wrong. The plan is one tune shared between three players who must "
                     "never move at the same moment. The fifth time through, the piano plays its high note a "
                     "sixteenth early and a semitone flat, and from then on its bar is one step too short: every "
                     "bar it arrives earlier and treads on the others, until the alarm is ringing its mistake back."),
              structure=[
                  "0:00 A watch ticking. It keeps this beat to the end and is never wrong.",
                  "0:02 The plan, one player at a time: bass, then the plucked string in the gaps, then the piano. No two ever move together.",
                  "0:21 Inside: the same figure a fourth higher, twice, clean.",
                  "0:30 Back in D for the fifth pass. At 0:33 the piano is a sixteenth early and a semitone flat (E flat for E). Everyone stops; a pad holds the wrong note.",
                  "0:37 They carry on, but the piano's bar is now 15 steps, so each bar it comes in one sixteenth earlier and lands on the others' notes.",
                  "0:46 The alarm: A and E flat, the piano's own slip, two octaves up. The bass has caught A flat, the plucks double, the tempo starts to push.",
                  "0:55 Running. Bass in straight eighths, the string falling down a diminished chord, the piano's loop shrinking to a trill on its mistake, the pad climbing a semitone a bar.",
                  "1:06 No last chord. Only the alarm and the watch, back at the plan's tempo.",
              ],
              reverb_db=-20, tail_ms=3000)

    keys = p.part("piano", "keys", role="top of the plan; the one who slips", gain_db=-3, pan=0.22)
    string = p.part("string", "string", role="plucks in the gaps of the plan", gain_db=-2, pan=-0.3)
    bass = p.part("bass", "bass_hollow", role="the plan's footsteps, later just running", gain_db=-4)
    kick = p.part("kick", "kick", role="the downbeat everyone counts from", gain_db=-5)
    hat = p.part("watch", "hat", role="a synchronised watch: ticks the beat, never wrong", gain_db=-8, pan=0.45)
    alarm = p.part("alarm", "bell", role="A and E flat, the piano's mistake rung back", gain_db=-8, pan=-0.5)
    dread = p.part("dread", "pad_wide", role="holds the wrong note, then climbs", gain_db=-11, pan=0.1,
                   lfo_shape="tri", lfo_rate=42, **{"lfo>cutoff": 5})

    TICK = 66   # the hat's note hardly matters
    plan = [(BASS_A, STRING_A, KEYS_A), (BASS_B, STRING_B, KEYS_B)]

    # ---- bars 1-8: the plan, taught one player at a time ------------------------------------------
    for cycle in range(4):
        for half, (b, s, k) in enumerate(plan):
            bar = 1 + 2 * cycle + half
            lay(bass, bar, b)
            if cycle >= 1:
                lay(string, bar, s)
            if cycle >= 2:
                lay(keys, bar, k)

    # ---- bars 9-12: inside, a fourth higher, twice -------------------------------------------------
    for i in range(4):
        b, s, k = plan[i % 2]
        lay(bass, 9 + i, b, up=5)
        lay(string, 9 + i, s, up=5)
        lay(keys, 9 + i, k, up=5)

    # ---- bars 13-14: back in D; the slip -----------------------------------------------------------
    lay(bass, 13, BASS_A)
    lay(string, 13, STRING_A)
    lay(keys, 13, KEYS_A)
    bass.play(14 * BAR, 3, "D2", 100)
    string.play(14 * BAR + 2, 1, "D3", 84)
    keys.play(14 * BAR + 3, 1, "A3", 78)
    keys.play(14 * BAR + 4, 9, "Eb4", 125)        # due on step 5 as E4. Nobody plays their next note.
    dread.play(14 * BAR + 6, 6 * BAR - 6.5, "Eb4", 70)   # the wrong note does not go away (to bar 20)

    # ---- bars 16-23: carrying on; the piano's bar is 15 steps --------------------------------------
    for k in range(8):
        bar, half, shaken = 16 + k, k % 2, k >= 4
        lay(bass, bar, ((BASS_A_SHAKEN, BASS_B_SHAKEN) if shaken else (BASS_A, BASS_B))[half])
        lay(string, bar, ((STRING_A_SHAKEN, STRING_B_SHAKEN) if shaken else (STRING_A, STRING_B))[half])
        cells = KEYS_B_WRONG if half else (KEYS_A_FLAT if shaken else KEYS_A)
        lay(keys, bar, cells, early=k)            # bar k of this stretch starts k sixteenths early
    dread.play(20 * BAR, 4 * BAR - 0.5, "Eb4", 92)

    # ---- bars 24-29: running -----------------------------------------------------------------------
    for i, row in enumerate(BASS_RUN):
        bass.line((24 + i) * BAR, row.split(), 2, velocity=[114, 88, 102, 88, 110, 88, 102, 92], hold=0.8)
    for i in range(6):
        lay(string, 24 + i, STRING_RUN_DOWN if i % 2 else STRING_RUN_UP, up=3 if i >= 4 else 0)
    for i, pitch in enumerate(["E4", "F4", "Gb4", "G4", "Ab4", "A4"]):   # a semitone a bar
        dread.play((24 + i) * BAR, BAR - 0.5, pitch, 100)

    # the piano has only its mistake left, and less and less room to play it in
    END = 30 * BAR
    step, i = 23 * BAR + 8, 0                      # where the last 15-step bar ended
    while step < END:
        gap = PANIC[i] if i < len(PANIC) else 2
        keys.play(step, 0.9, "A3", min(120, 92 + i))
        keys.play(step + 1, max(0.9, (gap - 1) * 0.9), "Eb4", min(127, 108 + i))
        step, i = step + gap, i + 1

    # ---- the alarm, from bar 20 and past the end ---------------------------------------------------
    for beat in range(4 * (30 - 20)):
        alarm.play(20 * BAR + 4 * beat, 3.6, "Eb6" if beat % 2 else "A5", 104)
    for beat, velocity in enumerate([104, 96, 88, 80, 70, 60]):          # bars 30-31: alone, getting further off
        alarm.play(30 * BAR + 4 * beat, 3.6, "Eb6" if beat % 2 else "A5", velocity)

    # ---- kick: the count ---------------------------------------------------------------------------
    for bar in list(range(1, 15)) + list(range(16, 20)):
        kick.play(bar * BAR, 2, 36, 100)
    for bar in range(20, 24):
        kick.play(bar * BAR, 2, 36, 108)
        kick.play(bar * BAR + 8, 2, 36, 96)
    for bar in range(24, 30):
        for beat in range(4):
            kick.play(bar * BAR + 4 * beat, 2, 36, 116 if beat == 0 else 106)

    # ---- the watch ---------------------------------------------------------------------------------
    for bar in range(32):
        for step in range(BAR):
            on_beat, on_eighth = step % 4 == 0, step % 2 == 0
            if bar >= 30:                          # alone again with the alarm
                velocity = [96, 64, 72, 64][step // 4] - (14 if bar == 31 else 0) if on_beat else 0
            elif bar >= 24:                        # sixteenths
                velocity = 96 if on_beat else 70 if on_eighth else 48
            elif bar >= 20:                        # eighths
                velocity = 92 if on_beat else 60 if on_eighth else 0
            elif bar >= 16:                        # the beat, and one nervous extra tick
                velocity = [96, 64, 72, 64][step // 4] if on_beat else 48 if step == 14 else 0
            elif 9 <= bar <= 12:                   # inside: quiet off-beats, things are going well
                velocity = [96, 64, 72, 64][step // 4] if on_beat else 40 if on_eighth else 0
            else:                                  # the beat, through the freeze as well
                velocity = [96, 64, 72, 64][step // 4] if on_beat else 0
            if velocity:
                hat.play(bar * BAR + step, 0.5, TICK, velocity)

    # ---- time: it pushes once the alarm is ringing, and snaps back to the watch's tempo at the cut ----
    p.tempo(20 * BAR, 24 * BAR, 1.0, 0.84)
    p.tempo(24 * BAR, 30 * BAR, 0.84, 0.76)
    return p.build()
