#!/usr/bin/env python3
"""Render welcome screenshots as WebP (1x and 2x, light and dark)."""

from __future__ import annotations

import base64
import io
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "tools" / "screens"
OUT = ROOT / "assets" / "img"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PORT = 9345
WIDTH = 3420
HEIGHT = 1700
WIDTHS = {"": 1000, "@2x": 2000}
SHOTS = ("step-pin", "step-open")


def recvn(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("socket closed")
        buf += chunk
    return buf


def ws_connect(url: str) -> socket.socket:
    rest = url[5:]
    hostport, path = rest.split("/", 1)
    host, port = hostport.split(":")
    sock = socket.create_connection((host, int(port)))
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET /{path} HTTP/1.1\r\n"
        f"Host: {hostport}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += sock.recv(4096)
    return sock


def ws_send(sock: socket.socket, text: str) -> None:
    data = text.encode()
    mask = os.urandom(4)
    frame = bytearray([0x81])
    n = len(data)
    if n < 126:
        frame.append(0x80 | n)
    elif n < 65536:
        frame.append(0x80 | 126)
        frame += struct.pack(">H", n)
    else:
        frame.append(0x80 | 127)
        frame += struct.pack(">Q", n)
    frame += mask
    frame += bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(frame)


def ws_recv(sock: socket.socket) -> str:
    while True:
        b0, b1 = recvn(sock, 2)
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        ln = b1 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", recvn(sock, 2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", recvn(sock, 8))[0]
        payload = recvn(sock, ln) if ln else b""
        if masked:
            mk = recvn(sock, 4)
            payload = bytes(b ^ mk[i % 4] for i, b in enumerate(payload))
        if opcode == 9:
            ws_send(sock, "")
            continue
        if opcode == 8:
            raise EOFError("websocket closed")
        if opcode == 1:
            return payload.decode()


class CDP:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._id = 0

    def call(
        self,
        method: str,
        params: dict | None = None,
        session_id: str | None = None,
        timeout: int = 200,
    ) -> dict:
        self._id += 1
        mid = self._id
        msg: dict = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        ws_send(self.sock, json.dumps(msg))
        for _ in range(timeout):
            raw = json.loads(ws_recv(self.sock))
            if raw.get("id") == mid:
                if "error" in raw:
                    raise RuntimeError(f"{method}: {raw['error']}")
                return raw.get("result", {})
        raise TimeoutError(method)


def wait_load(cdp: CDP, session_id: str) -> None:
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            cdp.sock.settimeout(0.5)
            raw = json.loads(ws_recv(cdp.sock))
        except socket.timeout:
            continue
        finally:
            cdp.sock.settimeout(None)
        if raw.get("method") == "Page.loadEventFired" and raw.get("sessionId") == session_id:
            return
    time.sleep(0.4)


def export(im: Image.Image, name: str, theme: str) -> None:
    if im.size != (WIDTH, HEIGHT):
        im = im.resize((WIDTH, HEIGHT), Image.LANCZOS)
    for suffix, out_w in WIDTHS.items():
        out_h = round(im.height * out_w / im.width)
        path = OUT / f"{name}-{theme}{suffix}.webp"
        im.resize((out_w, out_h), Image.LANCZOS).save(path, "WEBP", quality=86, method=6)
        print(f"  -> {path.relative_to(ROOT)} ({out_w}x{out_h})")


def main() -> int:
    if not CHROME.is_file():
        print(f"Chrome not found at {CHROME}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir=/tmp/blur-welcome-chrome-{PORT}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version") as resp:
                    ver = json.load(resp)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Chrome did not start")

        sock = ws_connect(ver["webSocketDebuggerUrl"])
        cdp = CDP(sock)
        target = cdp.call("Target.createTarget", {"url": "about:blank"})
        attached = cdp.call(
            "Target.attachToTarget",
            {"targetId": target["targetId"], "flatten": True},
        )
        sid = attached["sessionId"]

        def scall(method: str, params: dict | None = None) -> dict:
            return cdp.call(method, params, session_id=sid)

        scall("Page.enable")
        scall(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": WIDTH,
                "height": HEIGHT,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )

        for name in SHOTS:
            html = SCREENS / f"{name}.html"
            if not html.is_file():
                print(f"Missing {html}", file=sys.stderr)
                return 1
            for theme in ("light", "dark"):
                print(f"{html.name} ({theme})")
                scall(
                    "Emulation.setEmulatedMedia",
                    {"features": [{"name": "prefers-color-scheme", "value": theme}]},
                )
                scall("Page.navigate", {"url": html.as_uri()})
                wait_load(cdp, sid)
                time.sleep(0.25)
                shot = scall(
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": True},
                )
                im = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
                export(im, name, theme)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
