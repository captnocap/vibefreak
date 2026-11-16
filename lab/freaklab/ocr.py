"""Reads text off the emulated 128x64 display.

The firmware draws with a proportional pixel font, so reading it is a lookup:
cut a band of rows into runs of lit columns, and look each run up in a table
of shapes labelled once by eye (glyphs.json). A shape that is not in the table
comes back as '?' rather than a guess. The table stores a hash of each shape,
not the shape, so no part of the firmware's font is kept in this repository.

Capital I and lowercase l are the same shape in this font; a word that starts
with it is read as I.
"""
import hashlib
import json
import os
import re

GLYPH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glyphs.json")
TITLE_BAND = (2, 15)
VALUE_BAND = (51, 64)

_glyphs = None


def glyphs():
    global _glyphs
    if _glyphs is None:
        _glyphs = json.load(open(GLYPH_FILE)) if os.path.exists(GLYPH_FILE) else {}
    return _glyphs


def _columns(rows, band):
    top, bottom = band
    cols = []
    for x in range(128):
        bits = 0
        for y in range(top, bottom):
            if rows[y][x] == "#":
                bits |= 1 << (y - top)
        cols.append(bits)
    return cols


def shape_key(shape):
    return hashlib.sha1(shape.encode()).hexdigest()[:12]


def runs(rows, band, raw=False):
    """Yield (start_x, key, end_x) for each run of lit columns in the band.

    With raw=True the key is the shape itself (column bit patterns), which is
    what the labelling helper draws; otherwise it is the hash stored in the table.
    """
    cols = _columns(rows, band)
    x = 0
    while x < 128:
        if cols[x]:
            start = x
            while x < 128 and cols[x]:
                x += 1
            shape = ".".join(f"{c:x}" for c in cols[start:x])
            yield start, (shape if raw else shape_key(shape)), x
        else:
            x += 1


def read_line(rows, band):
    """All the text in a band as (text, gaps): gaps[i] is the dark width before character i."""
    table = glyphs()
    chars, gaps, last_end = [], [], None
    for start, key, end in runs(rows, band):
        chars.append(table.get(key, "?"))
        gaps.append(0 if last_end is None else start - last_end)
        last_end = end
    return chars, gaps


def _join(chars, gaps):
    out = ""
    for ch, gap in zip(chars, gaps):
        if out and gap >= 3:
            out += " "
        out += ch
    return re.sub(r"\bl(?=[a-z])", "I", out)


def read_screen(rows):
    """Title line and the label/value line of a parameter screen.

    The value is whatever follows the widest gap on the bottom line.
    """
    title = _join(*read_line(rows, TITLE_BAND))
    chars, gaps = read_line(rows, VALUE_BAND)
    if not chars:
        return {"title": title, "label": "", "value": ""}
    split = max(range(len(gaps)), key=lambda i: gaps[i])
    if gaps[split] < 4:
        return {"title": title, "label": _join(chars, gaps), "value": ""}
    return {
        "title": title,
        "label": _join(chars[:split], gaps[:split]),
        "value": _digits(_join(chars[split:], [0] + gaps[split + 1:])),
    }


def _digits(value):
    """The digit 1 is drawn with the same bar as l; in a value that has digits, it is a 1."""
    return value.replace("l", "1").replace("I", "1") if re.search(r"\d", value) else value
