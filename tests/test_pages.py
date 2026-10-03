import json
import subprocess
import sys
import zipfile
from pathlib import Path

from shogi_image_to_kif.browser import dispatch

ROOT = Path(__file__).resolve().parents[1]


def test_pages_build_contains_runtime_without_private_captures(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_site.py"),
            "--output",
            str(tmp_path),
        ],
        check=True,
    )
    with zipfile.ZipFile(tmp_path / "runtime.zip") as archive:
        names = archive.namelist()
    assert "shogi_image_to_kif/browser.py" in names
    assert "shogi_image_to_kif/assets/wars-templates.npz" in names
    assert not any(name.endswith((".png", ".traineddata")) for name in names)
    assert not (tmp_path / "local-samples").exists()
    page = (tmp_path / "index.html").read_text()
    assert "./backend.js" in page
    assert 'href="/style.css"' not in page
    rows = json.loads((tmp_path / "samples.json").read_text())
    assert len(rows) == 12
    assert all((tmp_path / row["file"]).exists() for row in rows)


def test_browser_bridge_exports_without_server_or_confirmation():
    result = json.loads(
        dispatch(
            json.dumps(
                {
                    "path": "/api/export",
                    "data": {
                        "preview": True,
                        "draft": {
                            "board": [None] * 81,
                            "hands": {"b": None, "w": None},
                            "turn": None,
                        },
                    },
                }
            )
        )
    )
    assert result["sfen"] == "sfen 9/9/9/9/9/9/9/9/9 b - 1"
    assert "先手番" in result["kif"]
    assert len(result["warnings"]) == 3
