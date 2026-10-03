import base64
import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from shogi_image_to_kif.domain.position import STARTING_SFEN
from shogi_image_to_kif.server import make_server

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def server():
    app = make_server(0, ROOT / "data/samples")
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    yield app
    app.shutdown()
    app.server_close()
    thread.join()


def request(server, path, value=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=30)
    body = json.dumps(value) if value is not None else None
    connection.request(
        "POST" if value is not None else "GET",
        path,
        body,
        headers or ({"Content-Type": "application/json"} if value is not None else {}),
    )
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, payload


def test_local_image_review_export(server):
    status, body = request(server, "/")
    assert status == 200
    assert b"Image" in body
    encoded = base64.b64encode(
        (ROOT / "data/samples/raw/Hisha ochi.png").read_bytes()
    ).decode()
    status, body = request(server, "/api/recognize", {"image": encoded, "ocr": False})
    assert status == 200
    draft = json.loads(body)
    status, _ = request(server, "/api/export", {"draft": draft, "reviewed": True})
    assert status == 400
    draft["turn"] = "w"
    draft["hands"] = {"b": {}, "w": {}}
    status, body = request(server, "/api/export", {"draft": draft, "reviewed": True})
    assert status == 200
    result = json.loads(body)
    assert result["sfen"] == "sfen " + STARTING_SFEN.replace("1r5b1", "7b1").replace(
        " b ", " w "
    )
    assert "後手番" in result["kif"]
    status, _ = request(server, "/api/export", {"draft": draft, "reviewed": False})
    assert status == 400


def test_invalid_inputs_and_cross_site_requests(server):
    status, _ = request(server, "/api/recognize", {"image": "not-base64"})
    assert status == 400
    status, _ = request(server, "/api/import-sfen", {"sfen": "invalid"})
    assert status == 400
    status, _ = request(
        server,
        "/api/import-sfen",
        {"sfen": STARTING_SFEN},
        {"Content-Type": "application/json", "Origin": "https://example.com"},
    )
    assert status == 403
    status, _ = request(server, "/", headers={"Host": "example.com"})
    assert status == 403
    status, _ = request(server, "/api/sample/../../pyproject.toml")
    assert status == 404
    status, body = request(server, "/api/samples")
    assert status == 200
    assert len(json.loads(body)) == 12


def test_preview_export_with_defaults_and_unusual_board(server):
    # Preserve recognized pieces, even an illustrative/incorrect five-gold board.
    draft = {
        "board": ["G"] * 5 + ["?"] + [None] * 75,
        "hands": {"b": None, "w": None},
        "turn": None,
    }
    status, body = request(server, "/api/export", {"draft": draft, "preview": True})
    assert status == 200
    result = json.loads(body)
    assert "先手番" in result["kif"]
    assert result["sfen"] == "sfen GGGGG4/9/9/9/9/9/9/9/9 b - 1"
    assert "未判別1マスを空マスとして出力" in result["warnings"]
    assert "金が5枚あります" in result["warnings"]
    assert any("持ち駒未指定" in text for text in result["warnings"])
    # Bad structure still fails, rather than emitting malformed KIF.
    draft["board"] = ["bogus"] * 81
    status, _ = request(server, "/api/export", {"draft": draft, "preview": True})
    assert status == 400
