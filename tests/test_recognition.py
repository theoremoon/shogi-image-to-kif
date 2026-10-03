import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from shogi_image_to_kif.domain.position import Position
from shogi_image_to_kif.recognition.grid import BoardNotFound, detect_grid, load_image
from shogi_image_to_kif.recognition.metadata import parse_hand, parse_metadata
from shogi_image_to_kif.recognition.pipeline import recognize

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "data/samples/manifest.json").read_text())
HELDOUT = [
    row
    for row in ROWS
    if row["annotation_status"] == "reviewed" and not row.get("template_source")
]


@pytest.mark.parametrize("row", HELDOUT, ids=lambda row: row["id"])
def test_heldout_board_images(row):
    image = load_image(ROOT / "data/samples" / row["file"])
    draft = recognize(image, ocr=False)
    expected = Position.from_sfen(row["sfen"])
    assert draft["board"] == expected.board
    assert draft["hands"] == {"b": None, "w": None}
    assert draft["turn"] is None
    assert not draft["reviewed"]


def test_rotated_jpeg_resized_board():
    row = next(row for row in ROWS if row["id"] == "commons-002")
    source = Image.open(ROOT / "data/samples" / row["file"]).convert("RGB")
    source = source.rotate(180).resize((553, 514))
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", quality=78)
    buffer.seek(0)
    draft = recognize(load_image(buffer), orientation="gote_bottom", ocr=False)
    assert draft["board"] == Position.from_sfen(row["sfen"]).board


@pytest.mark.parametrize("sample_id", ["commons-006", "commons-009", "commons-010"])
def test_reject_non_board_and_partial_diagrams(sample_id):
    row = next(row for row in ROWS if row["id"] == sample_id)
    with pytest.raises(BoardNotFound):
        detect_grid(load_image(ROOT / "data/samples" / row["file"]))


def test_manual_bounds_validate():
    image = np.full((200, 300, 3), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        detect_grid(image, [-1, 0, 200, 180])
    with pytest.raises(ValueError):
        detect_grid(image, [0, 0, float("nan"), 180])
    grid = detect_grid(image, [10, 10, 190, 190])
    assert grid.bounds == [10, 10, 190, 190]
    draft = recognize(image, bounds=[10, 10, 190, 190], ocr=False)
    assert draft["board"] == [None] * 81
    assert draft["hands"] == {"b": None, "w": None}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("飛二 銀 歩十二", {"R": 2, "S": 1, "P": 12}),
        ("なし", {}),
        ("歩18", {"P": 18}),
        ("歩19", None),
        ("銀かも", None),
        ("歩歩", None),
    ],
)
def test_hand_text(text, expected):
    assert parse_hand(text) == expected


def test_metadata_never_infers_turn_or_missing_hands():
    assert parse_metadata(["▲先手 なし"])["hands"] == {"b": None, "w": None}
    assert parse_metadata(["▲先手"])["turn"] is None
    value = parse_metadata(["先手の持駒：飛二 歩十二", "後手の持駒：なし", "後手番"])
    assert value["hands"] == {"b": {"R": 2, "P": 12}, "w": {}}
    assert value["turn"] == "w"
    assert parse_metadata(["先手番", "後手番"])["turn"] is None


def test_local_ocr_reads_actual_hand_when_available():
    import shutil

    if not shutil.which("tesseract"):
        pytest.skip("Tesseract is optional")
    image = load_image(ROOT / "data/samples/raw/2017-06-03a.png")
    draft = recognize(image)
    assert draft["hands"]["b"] == {"S": 1, "P": 2}
    assert draft["hands"]["w"] is None
    assert draft["turn"] is None


def test_invalid_multidigit_kanji_is_not_assumed_one():
    assert parse_hand("歩二一二") is None


def test_outer_border_covered_by_coordinate_labels():
    image = load_image(ROOT / "data/samples/raw/2017-06-03d.png")
    grid = detect_grid(image)
    # Simulate rank labels covering the right edge of an otherwise complete grid.
    right = round(grid.xs[-1])
    for row in range(9):
        middle = round((grid.ys[row] + grid.ys[row + 1]) / 2)
        image[middle - 15 : middle + 15, right - 3 : right + 5] = 255
    draft = recognize(image, ocr=False)
    row = next(row for row in ROWS if row["id"] == "commons-002")
    assert draft["board"] == Position.from_sfen(row["sfen"]).board


def test_real_piyo_screenshot_with_optional_ocr():
    import shutil

    path = ROOT / "data/local-samples/piyo-web-start.png"
    if not path.is_file() or not shutil.which("tesseract"):
        pytest.skip("Local-only Piyo capture and optional Tesseract are required")
    from shogi_image_to_kif.domain.position import STARTING_SFEN

    draft = recognize(load_image(path))
    assert draft["board"] == Position.from_sfen(STARTING_SFEN).board
    assert draft["review_squares"]  # unfamiliar font is still marked for human review


def test_wood_color_without_grid_is_rejected():
    image = np.full((438, 300, 3), [230, 168, 65], dtype=np.uint8)
    with pytest.raises(BoardNotFound):
        detect_grid(image)


@pytest.mark.parametrize("rotated", [False, True])
def test_local_wars_separate_board_and_uncertainty(rotated, monkeypatch):
    path = ROOT / "data/local-samples/wars-mate.png"
    bank = ROOT / "data/local-samples/wars-templates.npz"
    if not path.exists() or not bank.exists():
        pytest.skip("Run scripts/setup_wars.py for local-only Wars fixtures")
    monkeypatch.setenv("SHOGI_WARS_TEMPLATES", str(bank))
    expected = json.loads((ROOT / "data/annotations/wars-mate.json").read_text())[
        "board"
    ]
    image = load_image(path)
    if rotated:
        image = np.rot90(image, 2).copy()
    draft = recognize(
        image, orientation="gote_bottom" if rotated else "sente_bottom", ocr=False
    )
    errors = [i for i, (p, q) in enumerate(zip(draft["board"], expected)) if p != q]
    assert len(errors) <= 2
    assert all(i in draft["review_squares"] for i in errors)
    assert draft["hands"] == {"b": None, "w": None}
    assert draft["turn"] is None
    left, top, right, bottom = draft["board_bounds"]
    assert 0 <= left < right <= image.shape[1]
    assert 0 <= top < bottom <= image.shape[0]
