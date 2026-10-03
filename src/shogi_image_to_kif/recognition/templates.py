"""Shape matching against attributed reference glyphs, with uncertainty scores."""

import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import cv2
import numpy as np

SIZE = 40


def ink_mask(image: np.ndarray, *, wood=False) -> np.ndarray:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        # Black and red pieces both contrast with a light cell background.
        background = float(np.percentile(gray, 85))
        # Luminance keeps yellow last-move highlighting out of the foreground.
        threshold = min(120, background * 0.65) if wood else min(85, background * 0.55)
        mask = (gray < threshold).astype(np.uint8)
        if wood:
            hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            red = ((hsv[:, :, 0] < 8) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 160)
            # Official help overlays and red highlights are not character ink.
            mask[red] = 0
    else:
        mask = (image < 150).astype(np.uint8)
    # Discard tiny specks, disconnected coordinate dots and remnants at crop edges.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = np.zeros_like(mask)
    outline = any(
        (x == 0 or x + w >= mask.shape[1]) and h > mask.shape[0] * 0.55
        for x, y, w, h, area in stats[1:]
    )
    # Tiny dots distinguish 金 from 全; preserve them at screenshot resolution.
    minimum = max(1, mask.size * 0.0003)
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if wood and area < 5 and (y < 3 or y + h > mask.shape[0] - 3):
            continue
        if wood and (
            x == 0
            or x + w >= mask.shape[1]
            or ((y == 0 or y + h >= mask.shape[0]) and w > h * 2)
        ):
            continue
        if area < minimum:
            continue
        if (
            wood
            and outline
            and (
                (x == 0 or x + w >= mask.shape[1])
                and h > mask.shape[0] * 0.5
                or y > mask.shape[0] * 0.85
            )
        ):
            continue
        # A pentagonal piece outline is not a kanji stroke.
        if (
            w > mask.shape[1] * 0.85
            and h > mask.shape[0] * 0.85
            and area / (w * h) < 0.3
        ):
            continue
        cleaned[labels == i] = 1
    return cleaned


def normalize(mask: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(mask)
    if len(xs) < max(3, mask.size * 0.012):
        return None
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    # Normalize independently to accommodate rectangular cells and typography.
    return cv2.resize(
        cropped.astype(np.float32), (SIZE, SIZE), interpolation=cv2.INTER_AREA
    )


@lru_cache(maxsize=1)
def template_bank():
    path = files("shogi_image_to_kif").joinpath("assets/templates.npz")
    with np.load(str(path), allow_pickle=False) as data:
        return data["labels"].tolist(), data["masks"].astype(np.float32)


def classify(image: np.ndarray, *, wood=False) -> dict:
    mask = ink_mask(image, wood=wood)
    normalized = normalize(mask)
    if normalized is None:
        return {
            "piece": None,
            "score": 1.0,
            "margin": 1.0,
            "needs_review": False,
            "alternatives": [],
        }
    labels, bank = template_bank()
    if wood:
        path = Path(
            os.environ.get(
                "SHOGI_WARS_TEMPLATES",
                Path.cwd() / "data/local-samples/wars-templates.npz",
            )
        )
        if not path.is_file():
            path = Path(
                str(files("shogi_image_to_kif").joinpath("assets/wars-templates.npz"))
            )
        if path.is_file():
            with np.load(path, allow_pickle=False) as data:
                labels = labels + data["labels"].tolist()
                bank = np.concatenate([bank, data["masks"]])
    # Symmetric soft Dice and slight pixel translations tolerate rasterization.
    best = np.zeros(len(bank), dtype=np.float32)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        shifted = cv2.warpAffine(
            normalized, np.float32([[1, 0, dx], [0, 1, dy]]), (SIZE, SIZE)
        )
        intersection = np.sum(bank * shifted, axis=(1, 2))
        dice = (
            2
            * intersection
            / (np.sum(bank * bank, axis=(1, 2)) + np.sum(shifted * shifted) + 1e-6)
        )
        best = np.maximum(best, dice)
    by_piece = {}
    for label, score in zip(labels, best):
        by_piece[label] = max(by_piece.get(label, 0), float(score))
    top = sorted(by_piece.items(), key=lambda item: item[1], reverse=True)[:3]
    piece, score = top[0]
    margin = score - top[1][1]
    return {
        "piece": piece if score >= 0.43 else "?",
        "score": round(score, 4),
        "margin": round(margin, 4),
        "needs_review": score < 0.80 or margin < 0.07,
        "alternatives": [{"piece": p, "score": round(s, 4)} for p, s in top],
    }
