"""Loopback-only review app. Uploaded images are processed in memory."""

import base64
import binascii
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

from shogi_image_to_kif.domain.position import Position
from shogi_image_to_kif.exporters.draft import export_draft
from shogi_image_to_kif.recognition.grid import load_image
from shogi_image_to_kif.recognition.pipeline import recognize

MAX_BODY = 24 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024


def handler_factory(samples: Path):
    samples = samples.resolve()
    lock = threading.BoundedSemaphore(2)

    def rows():
        path = samples / "manifest.json"
        return json.loads(path.read_text()) if path.is_file() else []

    class Handler(BaseHTTPRequestHandler):
        def response(self, code, data, content_type="application/json; charset=utf-8"):
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False).encode()
            elif isinstance(data, str):
                data = data.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def allowed_host(self):
            port = self.server.server_port
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in allowed:
                self.response(403, {"error": "localhostからアクセスしてください"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed}:
                self.response(403, {"error": "別のサイトからの操作は受け付けません"})
                return False
            return True

        def do_GET(self):
            if not self.allowed_host():
                return
            path = urlsplit(self.path).path
            static = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]
                self.response(
                    200,
                    files("shogi_image_to_kif").joinpath(f"web/{name}").read_bytes(),
                    mime,
                )
            elif path == "/api/samples":
                self.response(
                    200,
                    [
                        {
                            key: row.get(key)
                            for key in ("id", "title", "kind", "source_url", "license")
                        }
                        for row in rows()
                        if (samples / row["file"]).is_file()
                    ],
                )
            elif path.startswith("/api/sample/"):
                record = next(
                    (
                        row
                        for row in rows()
                        if row["id"] == path.removeprefix("/api/sample/")
                    ),
                    None,
                )
                if record:
                    file = (samples / record["file"]).resolve()
                    if file.is_relative_to(samples) and file.is_file():
                        mime = (
                            "image/png"
                            if file.suffix.lower() == ".png"
                            else "image/jpeg"
                        )
                        self.response(200, file.read_bytes(), mime)
                        return
                self.response(404, {"error": "サンプルがありません"})
            else:
                self.response(404, {"error": "見つかりません"})

        def do_POST(self):
            if not self.allowed_host():
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self.response(415, {"error": "JSONで送信してください"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    self.response(
                        413, {"error": "画像ファイルは16MB以下にしてください"}
                    )
                    return
                value = json.loads(self.rfile.read(size))
                if not isinstance(value, dict):
                    raise ValueError("入力が不正です")
                if self.path == "/api/recognize":
                    if not lock.acquire(blocking=False):
                        self.response(
                            429, {"error": "認識中です。完了後に再試行してください"}
                        )
                        return
                    try:
                        data = base64.b64decode(
                            value["image"].split(",")[-1], validate=True
                        )
                        if len(data) > MAX_IMAGE_BYTES:
                            raise ValueError("画像ファイルは16MB以下にしてください")
                        image = load_image(io.BytesIO(data))
                        draft = recognize(
                            image,
                            bounds=value.get("bounds"),
                            orientation=value.get("orientation", "sente_bottom"),
                            ocr=value.get("ocr", True) is True,
                        )
                        self.response(200, draft)
                    finally:
                        lock.release()
                elif self.path == "/api/export":
                    self.response(200, export_draft(value))
                elif self.path == "/api/import-sfen":
                    position = Position.from_sfen(value["sfen"])
                    self.response(
                        200,
                        {
                            "board": position.board,
                            "hands": position.hands,
                            "turn": position.turn,
                            "move_number": position.move_number,
                            "cells": [],
                            "review_squares": [],
                            "notices": [],
                            "reviewed": False,
                        },
                    )
                else:
                    self.response(404, {"error": "見つかりません"})
            except (
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                OSError,
                binascii.Error,
            ) as exc:
                self.response(400, {"error": str(exc)})

    return Handler


def make_server(port=8765, samples=Path("data/samples")):
    return ThreadingHTTPServer(("127.0.0.1", port), handler_factory(samples))


def serve(port, samples):
    if not 0 <= port <= 65535:
        raise ValueError("ポートは0〜65535で指定してください")
    server = make_server(port, samples)
    print(
        f"画像を読み込み、盤面を確認してください: http://127.0.0.1:{server.server_port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
