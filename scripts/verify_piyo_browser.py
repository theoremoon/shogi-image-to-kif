"""Import generated positions in the live Piyo Shogi web app (fresh browser profile)."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    fixtures = json.loads((ROOT / "docs/compatibility-fixtures.json").read_text())
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1200})
        page.goto(
            "https://www.studiok-i.net/ps/",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_function(
            "typeof readKif === 'function' && typeof initGame === 'function'",
            timeout=30000,
        )
        page.evaluate(
            "document.querySelectorAll('img[data-src]').forEach(img => {img.src=img.dataset.src;})"
        )
        page.wait_for_function(
            "document.getElementById('U_FU')?.naturalWidth > 4", timeout=30000
        )
        for fixture in fixtures:
            imported = page.evaluate(
                """kif => {
                initGame(false);
                const result=readKif(kif);
                return {result, sfen:getCurrentBoardSFEN()};
            }""",
                fixture["kif"],
            )
            if imported["result"] != 0 or imported["sfen"] != fixture["sfen"]:
                raise AssertionError((fixture["name"], imported, fixture["sfen"]))
            results.append(
                {
                    "name": fixture["name"],
                    "imported_sfen": imported["sfen"],
                    "match": True,
                }
            )
        # A fresh screenshot exercises a real target font without redistributing it.
        page.evaluate(
            """() => {initGame(false);m_sStartBoard='startpos';initBoard();m_bInitDisp=false;m_nLoadedImgKomaCountDown=0;m_nLoadedAllImgCountDown=0;resizeBoard();drawBoard();closeDialogMessNoButton();}"""
        )
        directory = ROOT / "data/local-samples"
        directory.mkdir(exist_ok=True)
        page.locator("#shogi_board").screenshot(
            path=str(directory / "piyo-web-start.png")
        )
        (directory / "manifest.json").write_text(
            json.dumps(
                [
                    {
                        "id": "piyo-web-start",
                        "file": "piyo-web-start.png",
                        "source_url": "https://www.studiok-i.net/ps/",
                        "captured_at": "2026-10-03",
                        "kind": "screenshot",
                        "distribution": "local-only; not included in repository",
                        "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        browser.close()
    report = {
        "url": "https://www.studiok-i.net/ps/",
        "checked_at": "2026-10-03",
        "method": "Live web app in Chromium: initGame(false), readKif(kif), getCurrentBoardSFEN()",
        "results": results,
        "limitations": "スマホ版アプリの実機確認は含まない。",
    }
    (ROOT / "docs/piyo-browser-compatibility.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
