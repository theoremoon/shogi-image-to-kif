"""Detect complete axis-aligned 9x9 grids, rejecting partial diagrams."""

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps


class BoardNotFound(ValueError):
    pass


@dataclass
class Grid:
    xs: list[float]
    ys: list[float]
    score: float = 1.0
    wood: bool = False

    @property
    def bounds(self):
        return [self.xs[0], self.ys[0], self.xs[-1], self.ys[-1]]

    def cell(self, image: np.ndarray, row: int, col: int) -> np.ndarray:
        left, right = self.xs[col : col + 2]
        top, bottom = self.ys[row : row + 2]
        dx, dy = (right - left) * 0.10, (bottom - top) * 0.10
        return image[
            round(top + dy) : round(bottom - dy), round(left + dx) : round(right - dx)
        ]


def load_image(path) -> np.ndarray:
    with Image.open(path) as original:
        if original.width * original.height > 24_000_000:
            raise ValueError("画像は2400万画素以下にしてください")
        image = ImageOps.exif_transpose(original).convert("RGBA")
        base = Image.new("RGBA", image.size, "white")
        base.alpha_composite(image)
        return np.asarray(base.convert("RGB")).copy()


def _axis_lines(mask: np.ndarray, horizontal: bool):
    height, width = mask.shape
    length = max(12, round((width if horizontal else height) / 18))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (length, 1) if horizontal else (1, length)
    )
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    segments = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        span, thickness = (w, h) if horizontal else (h, w)
        if span >= length * 2 and thickness < span / 12:
            segments.append(
                (y + (h - 1) / 2, x, x + w)
                if horizontal
                else (x + (w - 1) / 2, y, y + h)
            )
    # Merge edges of thick board borders and minor line fragments.
    merged = []
    for pos, start, end in sorted(segments):
        if merged and abs(pos - merged[-1][0]) <= 3:
            p, s, e = merged[-1]
            merged[-1] = ((p + pos) / 2, min(s, start), max(e, end))
        else:
            merged.append((pos, start, end))
    return merged


def _sequences(lines):
    sequences = []
    positions = np.array([line[0] for line in lines])
    if len(positions) < 10:
        return sequences
    for first in range(len(lines) - 9):
        for last in range(first + 9, len(lines)):
            step = (positions[last] - positions[first]) / 9
            if step < 10:
                continue
            expected = positions[first] + np.arange(10) * step
            indices = np.abs(positions[:, None] - expected).argmin(axis=0)
            error = np.abs(positions[indices] - expected)
            if len(set(indices)) == 10 and error.max() <= max(2.5, step * 0.07):
                sequences.append(
                    ([lines[i] for i in indices], 1 - float(error.mean() / step))
                )
    return sequences


def _wood_grid(image: np.ndarray) -> Grid | None:
    """Find a broad wooden board, requiring periodic lines on both axes."""
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    wood = cv2.inRange(hsv, np.array([10, 55, 120]), np.array([40, 255, 255]))
    rows = ((wood > 0).mean(axis=1) > 0.7).astype(np.uint8)
    rows = cv2.morphologyEx(rows[:, None], cv2.MORPH_CLOSE, np.ones((7, 1), np.uint8))[
        :, 0
    ]
    indices = np.flatnonzero(rows)
    if not len(indices):
        return None
    runs = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(float)
    for run in sorted(runs, key=len, reverse=True):
        if len(run) < 90:
            continue
        top, bottom = int(run[0]), int(run[-1]) + 2
        columns = np.flatnonzero((wood[top:bottom] > 0).mean(axis=0) > 0.65)
        if not len(columns):
            continue
        left, right = int(columns[0]), int(columns[-1]) + 1
        if not 0.7 < (right - left) / (bottom - top) < 1.3:
            continue
        axes = []
        for profile, start, end in (
            (np.median(gray[top:bottom, left:right], axis=0), left, right),
            (np.median(gray[top:bottom, left:right], axis=1), top, bottom),
        ):
            step = (end - start) / 9
            positions, hits = [float(start)], 0
            for i in range(1, 9):
                expected = round(i * step)
                radius = max(2, round(step * 0.12))
                lo, hi = (
                    max(3, expected - radius),
                    min(len(profile) - 3, expected + radius + 1),
                )
                contrast = np.array(
                    [
                        (profile[j - 3] + profile[j + 3]) / 2 - profile[j]
                        for j in range(lo, hi)
                    ]
                )
                if not len(contrast):
                    break
                k = int(contrast.argmax())
                hits += contrast[k] > 3
                positions.append(float(start + lo + k))
            positions.append(float(end))
            if hits < 7 or len(positions) != 10:
                break
            axes.append(positions)
        if len(axes) == 2:
            return Grid(axes[0], axes[1], 0.8, wood=True)
    return None


def detect_grid(image: np.ndarray, bounds=None) -> Grid:
    height, width = image.shape[:2]
    if bounds is not None:
        if len(bounds) != 4 or not all(np.isfinite(v) for v in bounds):
            raise ValueError("盤領域は left,top,right,bottom の4座標です")
        left, top, right, bottom = bounds
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError("盤領域が画像の範囲外です")
        if min(right - left, bottom - top) < 90:
            raise ValueError("盤面が小さすぎます。各マス10px以上で指定してください")
        crop = image[round(top) : round(bottom), round(left) : round(right)]
        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        wood = (
            float(
                (
                    (hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 40) & (hsv[:, :, 1] > 55)
                ).mean()
            )
            > 0.7
        )
        return Grid(
            np.linspace(left, right, 10).tolist(),
            np.linspace(top, bottom, 10).tolist(),
            wood=wood,
        )
    factor = min(1, 1400 / max(height, width))
    resized = cv2.resize(image, (round(width * factor), round(height * factor)))
    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    # Adaptive threshold handles wood-colored backgrounds and JPEG noise.
    masks = [
        cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY_INV)[1],
        cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
        ),
    ]
    best = None
    for mask in masks:
        horizontal = _sequences(_axis_lines(mask, True))
        vertical_lines = _axis_lines(mask, False)
        vertical = _sequences(vertical_lines)
        for hs, hscore in horizontal:
            # App rank labels can cover the right outer border. Infer only
            # outer endpoints attested by all ten complete horizontal lines.
            augmented = list(vertical_lines)
            top, bottom = hs[0][0], hs[-1][0]
            for endpoint in (
                float(np.median([line[1] for line in hs])),
                float(np.median([line[2] - 1 for line in hs])),
            ):
                if not any(abs(line[0] - endpoint) < 4 for line in augmented):
                    augmented.append((endpoint, top, bottom))
            candidates = vertical + _sequences(sorted(augmented))
            for vs, vscore in candidates:
                xs, ys = [x[0] for x in vs], [y[0] for y in hs]
                bw, bh = xs[-1] - xs[0], ys[-1] - ys[0]
                if not 0.65 < bw / bh < 1.45:
                    continue
                tolerance = min(bw, bh) * 0.04
                hits = sum(
                    start <= xs[0] + tolerance and end >= xs[-1] - tolerance
                    for _, start, end in hs
                )
                hits += sum(
                    start <= ys[0] + tolerance and end >= ys[-1] - tolerance
                    for _, start, end in vs
                )
                if hits < 19:
                    continue
                score = (hscore + vscore) / 2
                # Prefer the largest complete grid in a multi-diagram image.
                rank = bw * bh * score
                if best is None or rank > best[0]:
                    best = (
                        rank,
                        Grid([x / factor for x in xs], [y / factor for y in ys], score),
                    )
    if best is None:
        wood = _wood_grid(image)
        if wood is not None:
            return wood
        raise BoardNotFound(
            "9×9の盤面を検出できませんでした。盤の左上・右下を指定してください。部分図・写真の斜め盤面は対象外です"
        )
    return best[1]
