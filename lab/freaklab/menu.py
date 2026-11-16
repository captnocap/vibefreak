"""Settings that live in the Utility menu rather than on a knob.

Only Utility > Preset > Modulations is driven here: Env Legato, Env Snap,
LFO Retrig, Press Mode, Key/Arp Mode and Velo Amp Mod. The menu is walked
the way a hand does it (Utility button, Preset encoder to move, click to go
in) and every step is checked against what the screen says.
"""
from . import ocr

LINE_TOPS = (18, 34, 50)

MODULATION_ITEMS = ["Env Legato", "Env Snap", "LFO Retrig", "Press Mode", "Key/Arp Mode", "Velo Amp Mod"]
OPTIONS = {
    "LFO Retrig": ["OFF", "ON", "Legato"],
    "Press Mode": ["Aftertouch", "Velocity"],
    "Key/Arp Mode": ["Linear", "Random"],
}


class MenuError(RuntimeError):
    pass


def _line(rows, top):
    """One text line near `top`; menu lines sit a row higher or lower depending on the screen."""
    best = None
    for t in range(top - 2, min(top + 3, 52)):
        chars, gaps = ocr.read_line(rows, (t, t + 13))
        cand = (chars.count("?"), abs(t - top), ocr._join(chars, gaps))
        if best is None or cand < best:
            best = cand
    return best[2]


def lines(lab):
    rows = lab.oled()
    return [_line(rows, top) for top in LINE_TOPS]


def title(lab):
    rows = ["".join("." if c == "#" else "#" for c in r) for r in lab.oled()]
    return ocr._join(*ocr.read_line(rows, ocr.TITLE_BAND))


def _selected(lab):
    """The menu line the arrow is on (the arrow and the scroll bar are not letters)."""
    for text in lines(lab):
        if text.startswith("?"):
            return text.strip("? ")
    return None


def _move_to(lab, want, limit=12):
    for direction in (1, -1):
        for _ in range(limit):
            if _selected(lab) == want:
                return
            lab.enc("preset", direction)
            lab.step(250)
    raise MenuError(f"menu entry '{want}' not found (on '{_selected(lab)}', screen '{title(lab)}')")


def _leave(lab):
    for _ in range(4):
        if "Utility" not in title(lab) and "Preset-" not in title(lab):
            return
        lab.click("utility", after_ms=350)


def set_modulation_option(lab, item, option):
    """Set one entry of Utility > Preset > Modulations and return what the screen then calls current."""
    if item not in OPTIONS:
        raise MenuError(f"'{item}' is not one of {sorted(OPTIONS)}")
    match = [o for o in OPTIONS[item] if o.lower() == str(option).lower()]
    if not match:
        raise MenuError(f"{item} is one of {OPTIONS[item]}")
    option = match[0]
    _leave(lab)
    lab.click("utility", after_ms=400)
    try:
        if title(lab) != "Utility":
            raise MenuError(f"Utility did not open (screen '{title(lab)}')")
        _move_to(lab, "Preset")
        lab.click("preset", after_ms=400)
        _move_to(lab, "Modulations")
        lab.click("preset", after_ms=400)
        _move_to(lab, item)
        lab.click("preset", after_ms=400)
        for direction in (1, -1):
            for _ in range(len(OPTIONS[item])):
                if lines(lab)[1] == option:
                    break
                lab.enc("preset", direction)
                lab.step(300)
            if lines(lab)[1] == option:
                break
        if lines(lab)[1] != option:
            raise MenuError(f"{item}: option '{option}' not offered (screen shows '{lines(lab)[1]}')")
        lab.click("preset", after_ms=400)
    finally:
        _leave(lab)
    return option


def set_key_mode(lab, mode):
    """Key/Arp source: 'linear' follows the note, 'random' draws a new value per note.

    A freshly loaded preset in the emulator behaves as Random while the menu
    says Linear, so Linear is always reached by going through Random first.
    """
    if mode.lower() == "linear":
        set_modulation_option(lab, "Key/Arp Mode", "Random")
    return set_modulation_option(lab, "Key/Arp Mode", mode)
