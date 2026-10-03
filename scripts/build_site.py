"""Build the GitHub Pages bundle with standard-library Python only."""

import argparse
import html
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/shogi_image_to_kif"


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    for name in ("app.js", "style.css"):
        shutil.copy2(PACKAGE / "web" / name, output / name)
    page = (PACKAGE / "web/index.html").read_text()
    page = page.replace(
        '<script src="./app.js"',
        '<script src="./backend.js" defer></script><script src="./app.js"',
    )
    page = page.replace(
        "<footer>黄色 = 要確認</footer>",
        '<footer>画像はブラウザ内で処理 · <a href="./credits.html">Credits</a></footer>',
    )
    page = page.replace(
        '<details id="ocr-detail"><summary>OCR</summary><pre id="ocr-text"></pre></details>',
        '<details id="ocr-detail" hidden><summary>OCR</summary><pre id="ocr-text"></pre></details>',
    )
    (output / "index.html").write_text(page)
    for name in ("backend.js", "worker.js"):
        shutil.copy2(ROOT / "site" / name, output / name)
    with zipfile.ZipFile(output / "runtime.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob("*.py")):
            if path.name not in ("server.py", "cli.py"):
                archive.write(
                    path, "shogi_image_to_kif/" + str(path.relative_to(PACKAGE))
                )
        for name in (
            "templates.npz",
            "templates-sources.json",
            "wars-templates.npz",
            "wars-template-sources.json",
        ):
            archive.write(
                PACKAGE / "assets" / name, "shogi_image_to_kif/assets/" + name
            )
    rows = json.loads((ROOT / "data/samples/manifest.json").read_text())
    public_rows = []
    for row in rows:
        source = ROOT / "data/samples" / row["file"]
        target = output / "samples" / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        public_rows.append({**row, "file": "samples/" + source.name})
    (output / "samples.json").write_text(
        json.dumps(public_rows, ensure_ascii=False, indent=2) + "\n"
    )
    shutil.copy2(ROOT / "LICENSE", output / "LICENSE.txt")
    shutil.copy2(ROOT / "docs/third-party.md", output / "third-party.txt")
    credits = [
        '<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Credits</title><link rel="stylesheet" href="./style.css"><main><a href="./">← Shogi</a><h1>Credits</h1><p>Code: MIT · <a href="./LICENSE.txt">License</a> · <a href="./third-party.txt">素材と依存</a></p>',
        '<p>Python runtime: <a href="https://pyodide.org/en/0.28.1/">Pyodide 0.28.1</a>, NumPy, OpenCV, Pillow. Runtime files are downloaded from jsDelivr. Browser release does not run Tesseract OCR.</p>',
        '<p>Wars glyph reference: <a href="https://shogiwars.heroz.jp/qa?locale=ja&amp;num=29">HEROZ / 将棋ウォーズ公式</a>. Extracted shape data retains the underlying material’s rights; screenshots are not bundled. App MIT license does not apply to this material.</p>',
        "<h2>Public samples</h2><ul>",
    ]
    for row in rows:
        credits.append(
            '<li><a href="'
            + html.escape(row["source_url"], quote=True)
            + '">'
            + html.escape(row["title"])
            + "</a> · "
            + html.escape(row.get("license", ""))
            + " · "
            + html.escape(row.get("author_html", ""))
            + "</li>"
        )
    credits.append(
        '</ul><p>Full attribution: <a href="./samples.json">samples.json</a></p></main></html>'
    )
    (output / "credits.html").write_text("\n".join(credits))
    (output / ".nojekyll").touch()
    print(
        f"Pages bundle: {output} ({sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) / 1024:.0f} KiB, excluding Pyodide downloads)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/site")
    build(parser.parse_args().output.resolve())
