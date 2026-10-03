"""Rebuild glyph references from reviewed board labels and installed Japanese fonts.

Reference image attribution is preserved in assets/templates-sources.json.
The distributed bank avoids depending on platform-specific fonts at runtime.
"""

import json
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from shogi_image_to_kif.domain.position import JAPANESE, Position
from shogi_image_to_kif.recognition.grid import detect_grid, load_image
from shogi_image_to_kif.recognition.templates import ink_mask, normalize

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/shogi_image_to_kif/assets"


def build():
    masks, labels, sources = [], [], []

    def add(mask, piece):
        value = normalize(mask)
        if value is not None:
            masks.extend([value, np.rot90(value, 2)])
            labels.extend([piece.upper(), piece.lower()])

    manifest = json.loads((ROOT / "data/samples/manifest.json").read_text())
    for annotation in sorted((ROOT / "data/annotations").glob("*.json")):
        record = json.loads(annotation.read_text())
        if not record.get("template_source"):
            continue
        source = next(row for row in manifest if row["id"] == record["sample_id"])
        image = load_image(ROOT / "data/samples" / source["file"])
        grid = detect_grid(image, record.get("board_bounds"))
        board = Position.from_sfen(record["sfen"]).board
        for index, piece in enumerate(board):
            if not piece:
                continue
            cell = ink_mask(grid.cell(image, index // 9, index % 9))
            if piece[-1].islower():
                cell = np.rot90(cell, 2)
            add(cell, piece)
        sources.append(
            {
                key: source[key]
                for key in (
                    "id",
                    "source_url",
                    "license",
                    "license_url",
                    "author_html",
                    "sha256",
                )
            }
        )

    candidates = list(Path("/System/Library/Fonts").glob("*.ttc"))
    candidates += list(Path("/usr/share/fonts").rglob("*CJK*"))
    candidates += list(Path("/usr/share/fonts").rglob("*IPA*"))
    font_paths = [
        p
        for p in candidates
        if any(
            word in unicodedata.normalize("NFC", p.name)
            for word in ("明朝", "ゴシック W3", "ゴシック W6", "CJK", "IPA")
        )
    ]
    aliases = {
        "K": ["玉", "王"],
        "+R": ["龍", "竜"],
        "+S": ["全", "成銀"],
        "+N": ["圭", "成桂"],
        "+L": ["杏", "成香"],
    }
    double = dict(
        zip(
            "PLNSGBRK", ("歩兵", "香車", "桂馬", "銀将", "金将", "角行", "飛車", "玉将")
        )
    )
    for path in font_paths:
        for piece, symbol in JAPANESE.items():
            symbols = aliases.get(piece, [symbol]) + (
                [double[piece]] if piece in double else []
            )
            for text in symbols:
                canvas = Image.new("L", (140, 180), 255)
                draw = ImageDraw.Draw(canvas)
                font = ImageFont.truetype(str(path), 90 if len(text) == 1 else 72)
                if len(text) == 1:
                    draw.text((20, 10), text, fill=0, font=font)
                else:
                    for row, char in enumerate(text):
                        draw.text((32, row * 78 - 4), char, fill=0, font=font)
                add(ink_mask(np.asarray(canvas)), piece)
    ASSETS.mkdir(exist_ok=True)
    np.savez_compressed(
        ASSETS / "templates.npz", labels=np.array(labels), masks=np.array(masks)
    )
    (ASSETS / "templates-sources.json").write_text(
        json.dumps(
            {
                "reference_images": sources,
                "rendered_fonts": [p.name for p in font_paths],
                "count": len(labels),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        f"Built {len(labels)} templates from {len(sources)} boards and {len(font_paths)} fonts"
    )


if __name__ == "__main__":
    build()
