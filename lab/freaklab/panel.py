"""A patch said the way it is set on the instrument's panel."""
from . import kb, matrix, patch


SWALLOWS_FIRST_NOTE = {"Modal"}


def modulation_lines(back, fields):
    """The modulation part of a patch, said the way it is set on the panel."""
    lines = []
    # Env > Cutoff is what the Filter Amount knob sets, and that knob is already listed
    shown = {k: v for k, v in back["matrix"].items() if k != "env>cutoff" or "env>cutoff" in fields}
    for point, amount in shown.items():
        src, dst = point.split(">")
        target = matrix.DEST_LABELS[dst]
        if dst.startswith("assign"):
            target += f" (= {back['assign'][dst]})"
        lines.append(f"  Matrix: {matrix.SOURCE_LABELS[src]} > {target}  {amount:+.1f}")
    used = {p.split(">")[0] for p in shown} | {p.split(">")[1] for p in shown}
    for i in (1, 2, 3):
        if f"assign{i}" in used and f"assign{i}" in fields:
            lines.append(f"  Assign{i}: hold the Assign{i} button and move {back['assign'][f'assign{i}']}")
    if "lfo" in used or any(k.startswith("lfo") for k in fields):
        rate = (f"Sync on, division {back['lfo_div']}" if back["lfo_sync"] else
                f"Sync off, {kb.lfo_rate_text(back['lfo_rate'])}")
        lines.append(f"  LFO: shape {back['lfo_shape']}, {rate}"
                     + (f", retrig {back['lfo_retrig']}" if back["lfo_retrig"] != "off" else ""))
    if "cyc_env" in used and back["cyc_amount"] <= 0.5:
        lines.append("  (CycEnv is routed but its Amount knob is at zero, so it does nothing)")
    for field, item in patch.MENU_FIELDS.items():
        if field in fields:
            lines.append(f"  Utility > Preset > Modulations > {item}: {fields[field]}")
    if "key_arp" in used and "key_mode" not in fields:
        lines.append("  Utility > Preset > Modulations > Key/Arp Mode: Linear")
    return lines


def describe(back, shown, fields):
    """The lines of the "On the panel" block for a patch that has been set and read back."""
    lines = [f"Type: {back['engine']}"]
    for knob in ("wave", "timbre", "shape"):
        s = shown[knob]
        lines.append(f"{s['label']}: {s['shown'] if s['shown'] is not None else str(back[knob]) + '%'}")
    lines.append(f"Filter: {str(back['filter']).upper()}   Amp Mod: {'on' if back['amp_mod'] else 'off'}"
                 f"   Paraphonic: {'on' if back['paraphonic'] else 'off'}")
    for knob in ("cutoff", "resonance", "attack", "decay", "sustain", "filter_amount"):
        lines.append(kb.knob_text(knob, back[knob]))
    if back["cyc_amount"] > 0.5:
        for knob in ("cyc_rise", "cyc_fall", "cyc_hold", "cyc_amount"):
            lines.append(kb.knob_text(knob, back[knob]))
    if back["glide"] > 0.5:
        lines.append(f"Glide: {back['glide']:.0f}% of the knob ({kb.clock(back['glide'])})")
    return lines + [line.strip() for line in modulation_lines(back, fields)]


def set_and_describe(lab, fields):
    """Put a patch on the instrument (on top of whatever is there) and return (read-back, screen, panel lines).

    Knobs go first and are read back while nothing modulates them: once the
    matrix is set, the firmware's table holds the moving values, not the knob
    positions.
    """
    patch.apply(lab, {k: v for k, v in fields.items() if not patch.is_point(k)})
    back = patch.read_back(lab)
    shown = patch.osc_display(lab)
    patch.apply(lab, {k: v for k, v in fields.items() if patch.is_point(k)})
    back["matrix"] = matrix.amounts(lab)
    if back["engine"] in SWALLOWS_FIRST_NOTE:
        # in the emulator this oscillator type gives nothing on the first note after it is
        # selected, so one note is played and left to die before anything is recorded
        lab.note_on(60, 100)
        lab.step(80)
        lab.note_off(60)
        lab.step(2500)
    return back, shown, describe(back, shown, fields)
