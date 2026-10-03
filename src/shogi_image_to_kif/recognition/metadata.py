"""Optional local Japanese OCR for explicitly labeled hands and turn.

OCR results remain candidates requiring review. Missing hands remain unknown.
"""

import re
import shutil
import subprocess
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path

import numpy as np
from PIL import Image

from shogi_image_to_kif.domain.position import HAND_ORDER, LIMITS

KANJI = dict(zip("歩香桂銀金角飛", "PLNSGBR"))


def number(text: str) -> int:
    if text.isdigit():
        return int(text)
    digits = dict(zip("一二三四五六七八九", range(1, 10)))
    if "十" in text:
        left, right = text.split("十", 1)
        return digits.get(left, 1) * 10 + digits.get(right, 0)
    return digits.get(text, 1)


def parse_hand(text: str) -> dict | None:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\s:：、・,]", "", text)
    if text in ("なし", "無し", "無", "0"):
        return {}
    # Ignore the Japanese "兵/車/将/行" suffix but never ignore other unknown text.
    parts = re.findall(
        r"([歩香桂銀金角飛])(?:兵|車|将|行)?([0-9一二三四五六七八九十]*)", text
    )
    if not parts:
        return None
    remaining = re.sub(
        r"([歩香桂銀金角飛])(?:兵|車|将|行)?([0-9一二三四五六七八九十]*)", "", text
    )
    if remaining:
        return None
    result = {}
    for piece, count in parts:
        label = KANJI[piece]
        if label in result:
            return None
        if count and not re.fullmatch(
            r"[1-9][0-9]*|[一二三四五六七八九]|十[一二三四五六七八九]?", count
        ):
            return None
        result[label] = number(count) if count else 1
        if not 1 <= result[label] <= LIMITS[label]:
            return None
    return {p: result[p] for p in HAND_ORDER if p in result}


def parse_metadata(texts: list[str]) -> dict:
    hands = {"b": None, "w": None}
    candidates = {"b": [], "w": []}
    turns = set()
    for text in texts:
        text = unicodedata.normalize("NFKC", text)
        compact = re.sub(r"\s", "", text)
        if re.search(r"先手番|手番[:：]先手", compact):
            turns.add("b")
        if re.search(r"後手番|手番[:：]後手", compact):
            turns.add("w")
        for side, names in (("b", "先手|下手"), ("w", "後手|上手")):
            # A player label alone is not evidence of zero pieces in hand.
            for match in re.finditer(
                rf"(?:{names})(?:の)?(?:持駒|持ち駒)[:：]?([^先後上下▲△▼▽]+)", compact
            ):
                hand = parse_hand(match.group(1))
                if hand is not None and hand not in candidates[side]:
                    candidates[side].append(hand)
            # Diagram margins may say "先手 銀 歩二" without "持駒".
            # Accept only complete nonempty piece lists on the same OCR line.
            for line in text.splitlines():
                line = re.sub(r"\s", "", line)
                match = re.search(rf"(?:{names})[:：]?(.+)$", line)
                if match:
                    hand = parse_hand(match.group(1))
                    if hand and hand not in candidates[side]:
                        candidates[side].append(hand)
    for side in hands:
        if len(candidates[side]) == 1:
            hands[side] = candidates[side][0]
    return {
        "hands": hands,
        "turn": next(iter(turns)) if len(turns) == 1 else None,
        "ocr_texts": [text.strip() for text in texts if text.strip()],
    }


def read_metadata(image: np.ndarray, grid) -> dict:
    executable = shutil.which("tesseract")
    if not executable:
        return {
            "hands": {"b": None, "w": None},
            "turn": None,
            "ocr_texts": [],
            "ocr_available": False,
        }
    left, top, right, bottom = map(round, grid.bounds)
    height, width = image.shape[:2]
    crops = [
        image[:top, :],
        image[bottom:, :],
        image[top:bottom, :left],
        image[top:bottom, right:],
    ]
    crops = [crop for crop in crops if crop.shape[0] >= 16 and crop.shape[1] >= 16]
    # Player labels may be rotated; vertical text uses PSM 5.
    tasks = [(crop, 6) for crop in crops] + [
        (crop, 5) for crop in crops if crop.shape[0] > 2 * crop.shape[1]
    ]
    # Outer side margins often include rank numbers in a separate inner column.
    if width - right >= 32:
        outer = image[top:bottom, right + round((width - right) * 0.38) :]
        if outer.shape[1] >= 16:
            tasks.append((outer, 5))
    tasks += [(np.rot90(crop, 2), 6) for crop in crops]
    assets = str(files("shogi_image_to_kif").joinpath("assets"))

    def recognize(task):
        crop, psm = task
        with tempfile.TemporaryDirectory(prefix="shogi-ocr-") as temporary:
            path = Path(temporary) / "crop.png"
            source = Image.fromarray(crop)
            scale = max(1, min(3, 1600 / max(source.size)))
            source = source.resize(
                (round(source.width * scale), round(source.height * scale))
            )
            source.save(path)
            try:
                result = subprocess.run(
                    [
                        executable,
                        str(path),
                        "stdout",
                        "--tessdata-dir",
                        assets,
                        "-l",
                        "jpn_vert" if psm == 5 else "jpn",
                        "--psm",
                        str(psm),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=12,
                    check=True,
                )
                return result.stdout
            except (subprocess.SubprocessError, OSError):
                return ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        texts = list(pool.map(recognize, tasks))
    result = parse_metadata(texts)
    result["ocr_available"] = True
    return result


def refine_gold_candidates(image: np.ndarray, grid, cells: list[dict]):
    """Use OCR only to disambiguate 金 vs similar promoted glyphs.

    Never infer a piece outside the shape recognizer's close alternatives.
    A change made by OCR still requires review.
    """
    from shogi_image_to_kif.recognition.templates import ink_mask, normalize

    executable = shutil.which("tesseract")
    if not executable:
        return
    suspects = []
    for index, cell in enumerate(cells):
        piece = cell["piece"]
        if not piece or piece.upper() not in ("+S", "+N", "+L"):
            continue
        gold = "G" if piece[-1].isupper() else "g"
        alternative = next(
            (
                candidate
                for candidate in cell["alternatives"]
                if candidate["piece"] == gold
            ),
            None,
        )
        if (
            alternative
            and alternative["score"] >= 0.65
            and cell["score"] - alternative["score"] <= 0.12
        ):
            suspects.append((index, gold, alternative["score"]))
    if not suspects:
        return
    assets = str(files("shogi_image_to_kif").joinpath("assets"))

    def recognize_gold(task):
        index, gold, score = task
        cell = grid.cell(image, index // 9, index % 9)
        if gold == "g":
            cell = np.rot90(cell, 2)
        mask = normalize(ink_mask(cell))
        if mask is None:
            return None
        with tempfile.TemporaryDirectory(prefix="shogi-glyph-") as temporary:
            path = Path(temporary) / "glyph.png"
            glyph = Image.fromarray((255 - mask * 255).astype(np.uint8)).resize(
                (160, 160)
            )
            canvas = Image.new("L", (220, 220), 255)
            canvas.paste(glyph, (30, 30))
            canvas.save(path)
            try:
                result = subprocess.run(
                    [
                        executable,
                        str(path),
                        "stdout",
                        "--tessdata-dir",
                        assets,
                        "-l",
                        "jpn",
                        "--psm",
                        "10",
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=6,
                    check=True,
                )
                if result.stdout.strip() == "金":
                    return index, gold, score
            except (subprocess.SubprocessError, OSError):
                pass
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(recognize_gold, suspects):
            if result:
                index, piece, score = result
                cells[index].update(
                    piece=piece, score=score, ocr_piece="金", needs_review=True
                )
