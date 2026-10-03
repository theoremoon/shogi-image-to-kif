"""Build local Wars glyph references and evaluate a separate board image."""

import io
import json
import os
from pathlib import Path

import numpy as np
from collect_wars_samples import main as collect
from PIL import Image

from shogi_image_to_kif.domain.position import Position
from shogi_image_to_kif.recognition.grid import detect_grid, load_image
from shogi_image_to_kif.recognition.pipeline import recognize
from shogi_image_to_kif.recognition.templates import ink_mask, normalize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/local-samples"


def main():
    collect()
    record = json.loads((ROOT / "data/annotations/wars-play.json").read_text())
    image = load_image(DATA / "wars-play.png")
    grid = detect_grid(image)
    masks, labels = [], []
    for index, piece in enumerate(Position.from_sfen(record["sfen"]).board):
        if not piece:
            continue
        glyph = normalize(ink_mask(grid.cell(image, index // 9, index % 9), wood=True))
        if glyph is not None:
            masks.extend([glyph, np.rot90(glyph, 2)])
            labels.extend([piece, piece.swapcase()])
    bank = DATA / "wars-templates.npz"
    np.savez_compressed(bank, masks=np.array(masks), labels=np.array(labels))
    os.environ["SHOGI_WARS_TEMPLATES"] = str(bank)
    (DATA / "wars-template-sources.json").write_text(
        json.dumps(
            {
                "reference": "wars-play",
                "count": len(labels),
                "source_url": record["source_url"],
                "distribution": "local-only; derived from official UI example",
                "heldout": "wars-mate",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    results = []
    for name in ["wars-play", "wars-mate"]:
        annotation = json.loads((ROOT / f"data/annotations/{name}.json").read_text())
        expected = (
            annotation.get("board") or Position.from_sfen(annotation["sfen"]).board
        )
        source = Image.open(DATA / (name + ".png")).convert("RGB")
        for variant in ["original", "jpeg", "rotated-jpeg", "resized-jpeg"]:
            orientation = "sente_bottom"
            if variant == "original":
                image = load_image(DATA / (name + ".png"))
            else:
                transformed = source
                if variant == "rotated-jpeg":
                    transformed = source.rotate(180)
                    orientation = "gote_bottom"
                if variant == "resized-jpeg":
                    transformed = source.resize((450, round(source.height * 1.5)))
                buffer = io.BytesIO()
                transformed.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)
                image = load_image(buffer)
            draft = recognize(image, orientation=orientation, ocr=False)
            errors = [
                i for i, (p, q) in enumerate(zip(draft["board"], expected)) if p != q
            ]
            if variant == "original":
                (DATA / (name + "-draft.json")).write_text(
                    json.dumps(draft, ensure_ascii=False, indent=2) + "\n"
                )
            results.append(
                {
                    "id": name,
                    "variant": variant,
                    "template_source": name == "wars-play",
                    "correct_squares": 81 - len(errors),
                    "errors": errors,
                    "review_squares": draft["review_squares"],
                    "errors_flagged": all(i in draft["review_squares"] for i in errors),
                    "auto_bounds": draft["board_bounds"],
                }
            )
    report = {
        "samples": results,
        "scope": "One reference and one separate official illustrated board; variants are correlated. Board only; hands and turn require manual input. Promoted rook/bishop remain weak.",
    }
    (ROOT / "docs/wars-evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    for row in results:
        print(
            row["id"],
            row["variant"],
            f"{row['correct_squares']}/81",
            "errors",
            row["errors"],
        )


if __name__ == "__main__":
    main()
