"""Talks to the vibefreak-lab process: one JSON line out, one JSON line back.

Emulated time only advances when a call asks for it, so the same script
always produces the same audio.
"""
import json
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB_BIN = os.environ.get("VIBEFREAK_LAB", os.path.join(REPO, "target", "release", "vibefreak-lab"))

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_number(note):
    """'C3' -> 48, '60' -> 60, or pass an int through.

    Names follow the instrument's own display, where the C at 130.8 Hz is C3
    (MIDI 48) and MIDI 69 is the 440 Hz A.
    """
    if isinstance(note, int):
        return note
    s = str(note).strip().upper().replace("♯", "#")
    if s.lstrip("-").isdigit():
        return int(s)
    name = s[:2] if len(s) > 2 and s[1] == "#" else s[:1]
    octave = int(s[len(name):])
    return NOTE_NAMES.index(name) + 12 * (octave + 1)  # C3 = 48


def note_hz(note):
    return 440.0 * 2 ** ((note_number(note) - 69) / 12)


class LabError(RuntimeError):
    pass


class Lab:
    def __init__(self, firmware=None, qspi=None, threads=2):
        if not os.path.exists(LAB_BIN):
            raise LabError(f"{LAB_BIN} is missing: run `cargo build --release -p vibefreak-lab`")
        cmd = [LAB_BIN]
        if firmware:
            cmd.append(firmware)
        if qspi:
            cmd += ["--qspi", qspi]
        env = dict(os.environ)
        env.setdefault("RAYON_NUM_THREADS", str(threads))
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, env=env)
        self.info = self._read()
        if not self.info.get("ok"):
            raise LabError(self.info.get("error", "emulator did not start"))

    def _read(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise LabError("vibefreak-lab exited")
            if line.startswith("{"):
                return json.loads(line)

    def call(self, op, **kw):
        kw["op"] = op
        self.proc.stdin.write(json.dumps(kw) + "\n")
        self.proc.stdin.flush()
        reply = self._read()
        if not reply.get("ok"):
            raise LabError(f"{op}: {reply.get('error')}")
        return reply

    def close(self):
        try:
            self.call("quit")
        except Exception:
            pass
        self.proc.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- time -----------------------------------------------------------
    def step(self, ms):
        return self.call("step", ms=ms)

    def render(self, ms, wav=None, raw_wav=None, cv_every=0):
        kw = {"ms": ms, "cv_every": cv_every}
        if wav:
            kw["wav"] = wav
        if raw_wav:
            kw["raw_wav"] = raw_wav
        return self.call("render", **kw)

    # --- playing --------------------------------------------------------
    def midi(self, *data):
        return self.call("midi", bytes=list(data))

    def note_on(self, note, velocity=100, channel=0):
        return self.midi(0x90 | channel, note_number(note), velocity)

    def note_off(self, note, channel=0):
        return self.midi(0x80 | channel, note_number(note), 0)

    def cc(self, number, value, channel=0):
        return self.midi(0xB0 | channel, number, max(0, min(127, int(value))))

    def key(self, key, pressure=200):
        return self.call("key", key=key, pressure=pressure)

    # --- panel ----------------------------------------------------------
    def pot(self, name, value):
        """Move a knob. value is 0..4095 (the full turn of the knob)."""
        return self.call("pot", name=name, value=int(value))

    def enc(self, name, delta):
        return self.call("enc", name=name, delta=int(delta))

    def click(self, name, hold_ms=60, after_ms=120):
        return self.call("click", name=name, hold_ms=hold_ms, after_ms=after_ms)

    def sw(self, name, pressed):
        return self.call("sw", name=name, pressed=bool(pressed))

    def filter_mode(self, mode):
        return self.call("filter_mode", mode=mode)

    # --- looking --------------------------------------------------------
    def oled(self):
        return self.call("oled")["rows"]

    def oled_png(self, path, scale=4):
        from PIL import Image
        rows = self.oled()
        img = Image.new("L", (128, 64))
        img.putdata([255 if c == "#" else 0 for row in rows for c in row])
        img.resize((128 * scale, 64 * scale), Image.NEAREST).save(path)
        return path

    def leds(self):
        return self.call("leds")

    def cv(self):
        return self.call("cv")

    def mem(self, addr, length):
        return bytes.fromhex(self.call("mem", addr=addr, len=length)["hex"])
