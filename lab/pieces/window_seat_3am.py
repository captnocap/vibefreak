"""Window Seat, 3 a.m.: the last bus, seen from the glass.

The bus is warm and nearly empty, the window is cold against your forehead, and there is nothing to
watch but the drops. The piece is that picture, with height on the glass as pitch. The street lamps
come past at exactly even intervals (one soft two-note swell a bar, the same lamp every time) and the
drops never do. A drop lands and hangs (one bell note, left to ring). Later a drop hangs, slips a
step or two, hangs again. Later still a running drop touches one that is hanging: both bells strike
the same note at once, left and right, and from there one drop carries on, heavier and faster.

The one thing that happens is a red light. The bus brakes (the lamps come slower), the road noise
dies, the engine idles on a C under the same lamp chord, which is lit differently for it, and in the
stillness one drop runs from the very top of the window to the very bottom, taking three others with
it. Then the light changes, the lamps start passing again, and a new drop lands at the top.

Time is in sixteenths at 60 BPM, so a step is a quarter of a second and a lamp passes every 4 s.
"""
from freaklab.compose import Piece

BAR = 16


def build():
    p = Piece("window_seat_3am", "Window Seat, 3 a.m.", bpm=60, steps_per_beat=4,
              about=("The last bus at three in the morning, from a window seat. The street lamps come past at "
                     "exactly even intervals; the drops on the glass never do. Each drop lands, hangs and slips "
                     "down, and when a running drop touches a hanging one the two bells strike together and fall "
                     "on as one, faster. Height on the glass is pitch."),
              reverb_db=-14, tail_ms=3500)

    # ---- the parts -------------------------------------------------------------------------------------
    left = p.part("drop_left", "bell", role="drops on the left of the glass; the runner at the red light",
                  gain_db=-3, pan=-0.5, decay=40)
    right = p.part("drop_right", "bell", role="drops on the right of the glass; the ones that hang and get collected",
                   gain_db=-3, pan=0.5, decay=40)
    lamp_low = p.part("lamp_low", "pad_warm", role="street lamp passing: B under one lamp, C sharp under the next",
                      gain_db=-8, pan=-0.3, attack=62, decay=55)
    lamp_high = p.part("lamp_high", "pad_wide", role="street lamp passing: the same F sharp every time",
                       gain_db=-8, pan=0.3, attack=62, decay=57)
    engine = p.part("engine", "bass_dark", role="the engine: E and A while moving, a quiet C while stopped",
                    gain_db=-6, pan=0.0, attack=30)
    road = p.part("road", "wind", role="tyres on the wet road; gone while the bus is stopped", gain_db=-8, pan=-0.1)
    roof = p.part("roof", "hat", role="rain on the roof, never evenly spaced", gain_db=-14, pan=0.15)

    # ---- the bus: brakes into the red light over bars 10-11, pulls away over bars 16-17 ------------------
    STOP, GREEN, END = 12 * BAR, 16 * BAR, 20 * BAR
    p.tempo(10 * BAR, STOP, 1.0, 1.4)
    p.tempo(GREEN, 18 * BAR, 1.4, 1.0)

    # ---- lamps and engine: the only regular things -------------------------------------------------------
    def moving(first_bar, strengths):
        """One lamp and one engine note a bar. Even bars: E under B and F sharp. Odd bars: A under C sharp and F sharp."""
        for i, v in enumerate(strengths):
            bar = first_bar + i
            lamp_low.play(bar * BAR, 7, "B3" if bar % 2 == 0 else "C#4", v)
            lamp_high.play(bar * BAR, 7, "F#4", v)
            engine.play(bar * BAR, 15, "E2" if bar % 2 == 0 else "A1", v)

    moving(0, [76, 76, 78, 78, 84, 84, 86, 86, 92, 94, 94, 90])
    # stopped: the lamp does not pass, it stands there; same two notes, but the floor under them is now C
    lamp_low.play(STOP, 61, "B3", 50)
    lamp_high.play(STOP, 61, "F#4", 50)
    engine.play(STOP, 62, "C2", 38)
    moving(16, [90, 86, 80, 70])

    road.play(0, 63.5, "C4", 72)
    road.play(4 * BAR, 63.5, "C4", 86)
    road.play(8 * BAR, 56, "C4", 98)             # let go half way through the braking
    road.play(GREEN + 3, 57, "C4", 88)

    # ---- rain on the roof: a fixed list of uneven gaps, squeezed or stretched by how hard it is raining ---
    gaps = [1.5, 2.5, 1, 3.5, 2, 1.25, 3, 1.75]
    accents = [1.0, 0.6, 0.85, 0.5, 0.75]
    ticks = ["F#4", "A#4", "D4"]                 # a hat hardly cares which note
    weather = [(24, 4 * BAR, 3.0, 44), (4 * BAR, 8 * BAR, 1.6, 56), (8 * BAR, 10 * BAR, 0.8, 70),
               (10 * BAR, STOP, 0.6, 80), (STOP, GREEN, 1.0, 62), (GREEN, 18 * BAR, 1.6, 54), (18 * BAR, END + 4, 3.0, 44)]
    n = 0
    for start, stop, spread, strength in weather:
        step = start
        while step < stop:
            roof.play(step, 0.4, ticks[n % 3], strength * accents[n % 5])
            step += gaps[n % 8] * spread
            n += 1

    # ---- the drops, written out ---------------------------------------------------------------------------
    def hang(part, step, pitch, velocity, ring=5):
        part.play(step, ring, pitch, velocity)

    def run(part, step, moves, velocity):
        """A drop on the move: (pitch, steps) one after another. Returns the step it ends on."""
        return part.line(step, [m[0] for m in moves], [m[1] for m in moves], velocity, hold=0.95)

    # bars 0-3: they land and stay where they are
    hang(left, 22.5, "B5", 62)
    hang(right, 34, "F#6", 54)
    hang(left, 41.5, "E6", 58)
    hang(right, 51, "A5", 70)
    hang(left, 59.5, "D6", 60)

    # bars 4-7: hang, slip, hang
    run(left, 67, [("F#6", 5), ("E6", 1), ("D6", 6)], [70, 56, 66])
    run(right, 78.5, [("B5", 4), ("A5", 1.5), ("G5", 1), ("F#5", 6)], [72, 58, 54, 68])
    run(left, 90, [("A6", 3.5), ("G6", 1), ("F#6", 1), ("E6", 4), ("D6", 1), ("C#6", 1), ("B5", 6)],
        [74, 58, 54, 70, 56, 54, 72])
    run(right, 101.5, [("E6", 4.5), ("D6", 1), ("B5", 4), ("A5", 1), ("G5", 0.5), ("F#5", 0.5), ("E5", 6)],
        [72, 58, 70, 60, 56, 56, 74])
    run(left, 114, [("D6", 3), ("C#6", 1), ("B5", 2.5), ("A5", 1), ("G5", 1), ("E5", 6)], [70, 56, 68, 58, 56, 72])

    # bars 8-9: the first meeting. One hangs on the right at A; the left one runs down into it.
    hang(right, 131.5, "A5", 72)
    meet = run(left, 134, [("G6", 3), ("F#6", 1), ("E6", 2.5), ("D6", 1), ("C#6", 1), ("B5", 1.5)],
               [74, 58, 70, 58, 56, 66])
    hang(right, meet, "A5", 84, ring=4)          # the touch: both bells on the same A
    run(left, meet, [("A5", 1.5), ("G5", 0.5), ("F#5", 0.5), ("E5", 0.5), ("D5", 0.5), ("B4", 2), ("A4", 0.5),
                     ("G4", 0.5), ("E4", 6)], [92, 80, 80, 82, 84, 96, 84, 86, 100])
    hang(right, 151.5, "D6", 64, ring=4)
    hang(right, 157, "F#6", 58, ring=4)

    # bars 10-11, while the bus brakes: the same thing the other way round, meeting on F sharp
    hang(left, 161, "F#5", 72)
    meet = run(right, 163.5, [("E6", 3), ("D6", 1), ("C#6", 2.5), ("B5", 1), ("A5", 1), ("G5", 1.5)],
               [74, 58, 70, 58, 56, 66])
    hang(left, meet, "F#5", 84, ring=4)
    run(right, meet, [("F#5", 1.5), ("E5", 0.5), ("D5", 0.5), ("C#5", 0.5), ("B4", 2), ("A4", 0.5), ("G4", 0.5),
                      ("F#4", 0.5), ("E4", 6)], [92, 80, 80, 82, 84, 96, 84, 86, 100])
    hang(left, 181, "B5", 62)
    hang(left, 187.5, "G6", 56, ring=4)

    # bars 12-15, stopped at the red light. Three land on the right and wait: G, C, and the C below.
    hang(right, STOP + 2.5, "G5", 66)
    hang(right, STOP + 8, "C6", 70)
    hang(right, STOP + 13.5, "C5", 68)
    # One lands at the very top of the glass, hangs, and goes: it meets each of the three in turn,
    # louder and quicker after every one, and does not stop until the bottom of the window.
    top = STOP + 18
    meet = run(left, top, [("B6", 4), ("A6", 1), ("G6", 2.5), ("F#6", 1), ("E6", 1), ("D6", 1.5)],
               [70, 58, 66, 58, 58, 62])
    hang(right, meet, "C6", 80, ring=2.8)
    meet = run(left, meet, [("C6", 1.5), ("B5", 0.75), ("A5", 0.75)], [86, 78, 80])
    hang(right, meet, "G5", 88, ring=2.4)
    meet = run(left, meet, [("G5", 1), ("F#5", 0.5), ("E5", 0.5), ("D5", 0.5)], [96, 88, 90, 92])
    hang(right, meet, "C5", 96)
    bottom = run(left, meet, [("C5", 1), ("B4", 0.5), ("A4", 0.5), ("G4", 0.5), ("F#4", 0.5), ("E4", 0.5),
                              ("D4", 0.5), ("C4", 8)], [106, 98, 100, 102, 104, 106, 108, 116])
    # and the glass starts to fill again
    hang(right, STOP + 49, "F#6", 52)
    hang(left, STOP + 56.5, "B5", 56)

    # bars 16-19, moving again: back to drops that mostly stay put
    hang(right, GREEN + 6, "E6", 60)
    run(left, GREEN + 17.5, [("A5", 4), ("G5", 1), ("F#5", 6)], [66, 54, 62])
    hang(right, GREEN + 31, "D6", 58)
    hang(left, GREEN + 41.5, "B5", 54)
    hang(right, GREEN + 53, "F#6", 50)
    last = END + 5
    hang(left, last, "B6", 46, ring=6)           # a new one at the top of the glass, where the big one began

    def clock(step):
        s = round(p._time(step) / 1000)
        return f"{s // 60}:{s % 60:02d}"

    p.structure = [
        f"{clock(0)} Moving. A lamp passes every four seconds (E, then A, under the same F sharp); single drops land and hang.",
        f"{clock(4 * BAR)} The drops start to slip: hang, a step or two down, hang again. The rain on the roof thickens.",
        f"{clock(8 * BAR)} First meeting: a drop on the left runs down into one hanging on the right, both bells strike the same A, and it falls on faster.",
        f"{clock(10 * BAR)} The bus brakes, the lamps come slower. The same meeting mirrored, right into left, on F sharp.",
        f"{clock(STOP)} Red light. No road noise, the engine idles on C, the lamp stands still. Three drops land on the right and wait.",
        f"{clock(top)} One drop from the top of the glass (B6) to the bottom (C4), collecting the three on the way, quicker after each. It lands at {clock(bottom - 8)}.",
        f"{clock(GREEN)} Green. The bus pulls away, lamps and road return, the drops go back to hanging.",
        f"{clock(last)} A new drop lands at the top of the glass.",
    ]
    p.humanize(ms=8, velocity=4)
    return p.build()
