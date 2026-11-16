"""The modulation matrix: five sources down the side, seven destinations across.

It is driven the way a hand drives it: turn the Matrix encoder to a point,
click, turn to set the amount, click again. Where the cursor is and what each
amount ended up as are read back from the firmware's memory (firmware
5.0.0.2084), so a point is never assumed to have been reached.

Amounts are percent, -100..100, as the screen shows them. One slow click of
the encoder is 0.1; the firmware speeds up when it is turned fast.

The last three destinations are whatever Assign1-3 point at. They are set as on
the panel: hold the Assign button and touch the control.
"""
import struct

from . import params

SOURCES = ["cyc_env", "env", "lfo", "pressure", "key_arp"]
DESTS = ["pitch", "wave", "timbre", "cutoff", "assign1", "assign2", "assign3"]
SOURCE_LABELS = {"cyc_env": "CycEnv", "env": "Env", "lfo": "LFO", "pressure": "Press", "key_arp": "Key/Arp"}
DEST_LABELS = {"pitch": "Pitch", "wave": "Wave", "timbre": "Timbre", "cutoff": "Cutoff",
               "assign1": "Assign1", "assign2": "Assign2", "assign3": "Assign3"}

CURSOR_ADDR = 0x200035A9          # one byte: row * 7 + column of the point the encoder is on
FIRST_SLOT = 23                   # word index in the voice table of CycEnv > Pitch
ASSIGN_SLOT = 19                  # word index of Assign1's destination; Assign2 and 3 follow
FULL = 32767

# What Assign can point at here: control -> (how to touch it, firmware parameter).
ASSIGNABLE = {
    "wave": ("enc", "VCO.Param1"), "timbre": ("enc", "VCO.Param2"), "shape": ("enc", "VCO.Param3"),
    "cutoff": ("pot", "VCF.Cutoff"), "resonance": ("pot", "VCF.Reso"),
    "attack": ("pot", "EG2.Attack"), "decay": ("pot", "EG2.DecRel"), "sustain": ("pot", "EG2.Sustain"),
    "filter_amount": ("pot", "EG2.Amount"),
    "cyc_rise": ("pot", "EG1.RiseLvl"), "cyc_fall": ("pot", "EG1.FallLvl"),
    "cyc_hold": ("pot", "EG1.Hold"), "cyc_amount": ("pot", "EG1.Amount"),
    "glide": ("pot", "Kbd.Glide"), "lfo_rate": ("enc", "LFO.Rate"),
}


class MatrixError(RuntimeError):
    pass


# The firmware names a destination by section and position: section number in the
# high byte, the parameter's place in that section in the low byte.
_SECTION = {"VCO": 0, "VCF": 1, "EG1": 2, "Kbd": 3, "Arp": 4, "LFO": 5, "EG2": 6}
_SECTION_NAMES = dict(params.VOICE_SECTIONS + params.PATCH_SECTIONS)


def _codes(control):
    """The codes that mean this control (LFO rate has one for free running and one for synced)."""
    if control == "filter_amount":
        return (0x0D01,)
    sec, name = ASSIGNABLE[control][1].split(".")
    code = (_SECTION[sec] << 8) | _SECTION_NAMES[sec].index(name)
    return (code, 0x0501) if control == "lfo_rate" else (code,)


ASSIGN_CODES = {c: name for name in ASSIGNABLE for c in _codes(name)}


def parse_point(text):
    """'lfo>cutoff', 'lfo:cutoff' or 'LFO > Cutoff' -> ('lfo', 'cutoff')."""
    s = text.lower().replace(" ", "").replace("/", "_").replace(":", ">")
    if ">" not in s:
        raise MatrixError(f"'{text}' is not source>destination")
    src, dst = s.split(">", 1)
    src = {"cycenv": "cyc_env", "cyc": "cyc_env", "press": "pressure", "key": "key_arp", "keyarp": "key_arp",
           "arp": "key_arp", "envelope": "env"}.get(src, src)
    dst = dst.replace("assign_", "assign")
    if src not in SOURCES or dst not in DESTS:
        raise MatrixError(f"'{text}': sources are {SOURCES}, destinations are {DESTS}")
    return src, dst


def _slot(src, dst):
    return FIRST_SLOT + 6 * DESTS.index(dst) + SOURCES.index(src)


def _word(lab, index):
    return struct.unpack("<h", lab.mem(params.VOICE_BASE + 2 * index, 2))[0]


def amounts(lab):
    """Every point that is not zero, as {'lfo>cutoff': percent}."""
    n = 6 * len(DESTS)
    raw = struct.unpack(f"<{n}h", lab.mem(params.VOICE_BASE + 2 * FIRST_SLOT, 2 * n))
    out = {}
    for d, dst in enumerate(DESTS):
        for s, src in enumerate(SOURCES):
            v = raw[6 * d + s]
            if v:
                out[f"{src}>{dst}"] = round(v * 100 / FULL, 1)
    return out


def assignments(lab):
    """What Assign1-3 point at: a control name where it is one this module knows, else the raw code."""
    raw = struct.unpack("<3H", lab.mem(params.VOICE_BASE + 2 * ASSIGN_SLOT, 6))
    return {f"assign{i + 1}": ASSIGN_CODES.get(v, f"code {v:#06x}") for i, v in enumerate(raw)}


def _cursor(lab):
    return lab.mem(CURSOR_ADDR, 1)[0]


def _goto(lab, src, dst):
    want = SOURCES.index(src) * 7 + DESTS.index(dst)
    for _ in range(80):
        here = _cursor(lab)
        if here == want:
            lab.step(120)
            if _cursor(lab) == want:
                return
            continue
        lab.enc("matrix", 1 if want > here else -1)  # one point per turn, however far it is told to go
        lab.step(150)
    raise MatrixError(f"could not reach {src}>{dst}")


# encoder clicks sent in one go -> how far the stored amount moves
_STRIDES = [(20, 10240), (10, 5120), (5, 1280), (3, 384), (2, 256), (1, 32)]


def set_amount(lab, src, dst, percent):
    """Set one point and return the amount the firmware now holds, in percent."""
    if not -100 <= percent <= 100:
        raise MatrixError("matrix amounts run -100..100")
    target = round(percent * FULL / 100)
    slot = _slot(src, dst)
    if abs(_word(lab, slot) - target) <= 16:
        return round(_word(lab, slot) * 100 / FULL, 1)
    _goto(lab, src, dst)
    lab.click("matrix", after_ms=250)
    try:
        stuck = 0
        for _ in range(200):
            now = _word(lab, slot)
            err = target - now
            if abs(err) <= 16:
                break
            clicks = next((c for c, move in _STRIDES if move <= abs(err)), 1)
            lab.enc("matrix", clicks if err > 0 else -clicks)
            lab.step(60)
            if _word(lab, slot) == now:
                stuck += 1
                if stuck > 3:  # at the end of its travel, or the click never opened the point
                    break
            else:
                stuck = 0
    finally:
        lab.step(200)  # a click straight after a turn takes the last turn back
        lab.click("matrix", after_ms=200)
    got = _word(lab, slot)
    if abs(got - target) > 40:
        raise MatrixError(f"{src}>{dst}: wanted {percent}, firmware holds {got * 100 / FULL:.1f}")
    return round(got * 100 / FULL, 1)


def clear(lab):
    """Zero every point that is not zero."""
    for point in amounts(lab):
        set_amount(lab, *parse_point(point), 0)


def assign(lab, slot, control):
    """Point Assign1, 2 or 3 at a control, by holding the button and touching it."""
    if slot not in (1, 2, 3):
        raise MatrixError("assign slot is 1, 2 or 3")
    control = control.lower()
    if control not in ASSIGNABLE:
        raise MatrixError(f"assign: '{control}' is not one of {sorted(ASSIGNABLE)}")
    how, param = ASSIGNABLE[control]
    want = _codes(control)
    index = ASSIGN_SLOT + slot - 1
    if _word(lab, index) in want:
        return
    held = params.read(lab, param)
    for _ in range(3):
        lab.sw(f"assign_{slot}", True)
        lab.step(300)
        if how == "enc":
            lab.enc(control, 1)
        else:
            lab.pot(control, 1200)
            lab.step(120)
            lab.pot(control, 1700)
        lab.step(300)
        lab.sw(f"assign_{slot}", False)
        lab.step(300)
        if _word(lab, index) in want:
            if params.read(lab, param) != held:
                raise MatrixError(f"assigning {control} moved it: set the knobs after the assignments")
            return
    raise MatrixError(f"could not point Assign{slot} at {control}")
