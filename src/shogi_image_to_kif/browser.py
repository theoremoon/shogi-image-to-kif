"""JSON bridge for the Pyodide worker; image bytes never leave the browser."""

import base64
import io
import json

from shogi_image_to_kif.domain.position import Position
from shogi_image_to_kif.exporters.draft import export_draft
from shogi_image_to_kif.recognition.grid import load_image
from shogi_image_to_kif.recognition.pipeline import recognize


def dispatch(request_json: str) -> str:
    request = json.loads(request_json)
    value = request["data"]
    if request["path"] == "/api/recognize":
        raw = base64.b64decode(value["image"].split(",")[-1], validate=True)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("画像は16MB以下にしてください")
        result = recognize(
            load_image(io.BytesIO(raw)),
            bounds=value.get("bounds"),
            orientation=value.get("orientation", "sente_bottom"),
            ocr=False,
        )
    elif request["path"] == "/api/export":
        result = export_draft(value)
    elif request["path"] == "/api/import-sfen":
        position = Position.from_sfen(value["sfen"])
        result = {
            "board": position.board,
            "hands": position.hands,
            "turn": position.turn,
            "move_number": position.move_number,
            "cells": [],
            "review_squares": [],
            "notices": [],
            "reviewed": False,
        }
    else:
        raise ValueError("Unknown operation")
    return json.dumps(result, ensure_ascii=False)
