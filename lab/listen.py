#!/usr/bin/env python3
"""The listening page: every render in lab/out/, newest first, playable in a browser.

  lab/listen.py [--port 8770] [--dir lab/out]

Python standard library only. It reads the folder on every request, so a new
`freak play` render shows up by itself. It never writes, renames or deletes.
Open to the home network and the VPN client ranges only; there is no login.
"""
import argparse
import http.server
import ipaddress
import json
import os
import re
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "web", "listen.html")
ALLOWED = [ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "::1/128",
    "10.0.0.0/24", "10.2.0.0/24",          # home LAN
    "192.168.10.0/24", "192.168.4.0/24",   # WireGuard and Teleport clients
)]
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def renders(folder):
    """Every full-output recording in the folder with what is known about it, newest first."""
    out = []
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return out
    for fn in names:
        if not fn.endswith(".wav") or fn.endswith(".osc.wav") or fn.startswith("_"):
            continue
        name = fn[:-4]
        if not SAFE_NAME.match(name):
            continue
        path = os.path.join(folder, fn)
        try:
            st = os.stat(path)
            with wave.open(path, "rb") as w:
                seconds = w.getnframes() / w.getframerate()
                rate = w.getframerate()
        except (OSError, wave.Error, EOFError):
            continue  # still being written, or not a recording
        item = {"name": name, "mtime": int(st.st_mtime), "seconds": round(seconds, 2), "rate": rate,
                "oscillator_file": os.path.exists(os.path.join(folder, name + ".osc.wav")), "card": None}
        try:
            with open(os.path.join(folder, name + ".json")) as fh:
                card = json.load(fh)
            # a details file older than the recording describes an earlier render of the same name
            if os.path.getmtime(os.path.join(folder, name + ".json")) >= st.st_mtime - 2:
                item["card"] = card
        except (OSError, ValueError):
            pass
        out.append(item)
    out.sort(key=lambda r: -r["mtime"])
    return out


class Handler(http.server.BaseHTTPRequestHandler):
    folder = "."
    server_version = "freak-listen"

    def allowed(self):
        try:
            addr = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        if addr.version == 6 and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        return any(addr in net for net in ALLOWED if net.version == addr.version)

    def send_bytes(self, body, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_audio(self, path):
        """A recording, whole or as the byte range the browser asked for (players need ranges to seek)."""
        try:
            size = os.path.getsize(path)
            fh = open(path, "rb")
        except OSError:
            return self.send_bytes(b"not found\n", "text/plain", 404)
        with fh:
            start, end = 0, size - 1
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
            partial = False
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                partial = True
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.command == "HEAD":
                return
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(65536, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        if not self.allowed():
            return self.send_bytes(b"this page is for the home network only\n", "text/plain", 403)
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            try:
                with open(PAGE, "rb") as fh:
                    return self.send_bytes(fh.read(), "text/html; charset=utf-8")
            except OSError:
                return self.send_bytes(b"listen.html is missing\n", "text/plain", 500)
        if path == "/api/renders":
            body = json.dumps({"renders": renders(self.folder)}).encode()
            return self.send_bytes(body, "application/json")
        m = re.fullmatch(r"/audio/([^/]+)\.wav", path)
        if m:
            name = m.group(1)
            stem = name[:-4] if name.endswith(".osc") else name
            if SAFE_NAME.match(stem) and ".." not in name:
                return self.send_audio(os.path.join(self.folder, name + ".wav"))
        self.send_bytes(b"not found\n", "text/plain", 404)

    do_HEAD = do_GET

    def log_message(self, fmt, *args):
        pass  # one line per audio range request is noise in the journal


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--dir", default=os.path.join(HERE, "out"))
    args = ap.parse_args()
    Handler.folder = os.path.abspath(args.dir)
    os.makedirs(Handler.folder, exist_ok=True)
    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"listening page on http://{args.bind}:{args.port}/ serving {Handler.folder}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
