"""The firmware's live parameter table.

Firmware 5.0.0.2084 keeps the current patch as a flat list of 16-bit values at
0x20008880 (oscillator, envelope) and 0x2001DA74 (the rest), in the same order the preset file stores them (found by sending
MIDI CCs and watching which words changed). Values run 0..32767.

Only the names and the order are taken on trust from the preset format; every
one used by the tools is checked against a control change before being relied
on (see `freak selftest`).
"""
import struct

# Two tables. The per-voice one holds the oscillator and the main envelope;
# everything else sits in the patch-wide one.
VOICE_BASE = 0x20008880
VOICE_SECTIONS = [
    ("VCO", ["Type", "Param1", "ParaX1", "Param2", "ParaX2", "Param3", "ParaX3", "BendRng", "Pitch", "SmpIdx"]),
    ("EG2", ["Mode", "Attack", "DecRel", "Sustain", "Legato", "Amount", "Snap"]),
]
PATCH_BASE = 0x2001DA74
PATCH_SECTIONS = [
    ("VCF", ["Type", "Cutoff", "Reso"]),
    ("EG1", ["Mode", "RiseLvl", "RiseSlp", "FallLvl", "Hold", "FallSlp", "Amount"]),
    ("Kbd", ["Glide", "Octave", "Veloc", "Hold", "GlMode", "PresAmp", "Scale", "Root"]),
    ("Arp", ["Enable", "Range", "Div", "Rate", "Swing", "Sync", "Spice", "Dice", "Dir", "SeqOn"]),
    ("LFO", ["Shape", "Div", "Rate", "Sync", "Retrig"]),
    ("Gen", ["Parafon", "Panel", "PolyCnt", "PrstVol", "Volume", "UniSprd", "UniCnt", "Chord",
             "ChOffs1", "ChOffs2", "ChOffs3", "SmpHash"]),
    ("Sys", ["PrsetID", "PrsetBt", "Save", "Utility", "Shift", "ShfLED"]),
    ("Mat", ["MatEnc", "MatBtn", "Assign1", "Assign2", "Assign3", "KyMdSrc"]),
    ("Seq", ["Length", "XiceRst", "GateLen", "Smooth1", "Smooth2", "Smooth3", "Smooth4"]),
]


def _names(sections):
    return [f"{sec}.{name}" for sec, names in sections for name in names]


VOICE_NAMES = _names(VOICE_SECTIONS)
PATCH_NAMES = _names(PATCH_SECTIONS)
ADDRESS = {n: VOICE_BASE + 2 * i for i, n in enumerate(VOICE_NAMES)}
ADDRESS.update({n: PATCH_BASE + 2 * i for i, n in enumerate(PATCH_NAMES)})


def read_all(lab):
    out = {}
    for base, names in ((VOICE_BASE, VOICE_NAMES), (PATCH_BASE, PATCH_NAMES)):
        raw = lab.mem(base, 2 * len(names))
        out.update(zip(names, struct.unpack(f"<{len(names)}H", raw)))
    return out


def read(lab, name):
    return struct.unpack("<H", lab.mem(ADDRESS[name], 2))[0]
