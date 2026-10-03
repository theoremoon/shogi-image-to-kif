"""Image -> reviewable position draft, never guessing unobserved metadata."""

from hashlib import sha256

import numpy as np

from shogi_image_to_kif.recognition.grid import detect_grid
from shogi_image_to_kif.recognition.metadata import (
    read_metadata,
    refine_gold_candidates,
)
from shogi_image_to_kif.recognition.templates import classify


def recognize(
    image: np.ndarray, *, bounds=None, orientation="sente_bottom", ocr=True
) -> dict:
    if orientation not in ("sente_bottom", "gote_bottom"):
        raise ValueError("盤の向きを指定してください")
    original = image
    if orientation == "gote_bottom":
        image = np.rot90(image, 2).copy()
        if bounds is not None:
            left, top, right, bottom = bounds
            height, width = image.shape[:2]
            bounds = [width - right, height - bottom, width - left, height - top]
    grid = detect_grid(image, bounds)
    cells = [
        classify(grid.cell(image, i // 9, i % 9), wood=grid.wood) for i in range(81)
    ]
    if ocr:
        refine_gold_candidates(image, grid, cells)
    meta = (
        read_metadata(image, grid)
        if ocr
        else {
            "hands": {"b": None, "w": None},
            "turn": None,
            "ocr_texts": [],
            "ocr_available": False,
        }
    )
    notices = [
        "候補の盤面を原画像と照合してください。黄色のマスは特に確認が必要です。",
        "持ち駒と手番は画像で読めない場合、手入力してください。",
    ]
    display_bounds = grid.bounds
    if orientation == "gote_bottom":
        left, top, right, bottom = display_bounds
        height, width = image.shape[:2]
        display_bounds = [width - right, height - bottom, width - left, height - top]
    # Similarity is a ranking score, not a calibrated probability.
    return {
        "schema_version": 1,
        "board": [c["piece"] for c in cells],
        "cells": cells,
        "hands": meta["hands"],
        "turn": meta["turn"],
        "move_number": 1,
        "orientation": orientation,
        "board_bounds": display_bounds,
        "image_size": [image.shape[1], image.shape[0]],
        "image_sha256": sha256(original.tobytes()).hexdigest(),
        "review_squares": [i for i, c in enumerate(cells) if c["needs_review"]],
        "ocr_texts": meta["ocr_texts"],
        "ocr_available": meta["ocr_available"],
        "notices": notices,
        "reviewed": False,
    }
