"""Exercise image upload, correction, review, and download in a real browser."""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=int, default=30000)
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.locator("#image-file").set_input_files(
            ROOT / "data/samples/raw/Hisha ochi.png"
        )
        expect(page.locator("#source-canvas")).to_be_visible()
        page.locator("#recognize").click()
        expect(page.locator("#board .square")).to_have_count(81, timeout=args.timeout)
        expect(page.locator("#export")).to_be_enabled()
        # Export immediately without setting turn, hands, or confirmation.
        page.locator("#export").click()
        expect(page.locator("#output-area")).to_be_visible()
        assert "先手番" in page.locator("#output-text").input_value()
        assert "未指定" in page.locator("#output-warnings").inner_text()
        # Change one square, then undo the edit.
        page.get_by_role("button", name="先手の歩を置く", exact=True).click()
        page.locator("#board .square").nth(40).click()
        expect(page.locator("#board .square").nth(40)).to_have_text("歩")
        page.locator("#undo").click()
        expect(page.locator("#board .square").nth(40)).to_have_text("")
        page.locator("#turn").select_option("w")
        expect(page.locator("#export")).to_be_enabled()
        page.locator("#export").click()
        expect(page.locator("#output-area")).to_be_visible()
        assert "後手番" in page.locator("#output-text").input_value()
        page.locator("#output-format").select_option("sfen")
        assert page.locator("#output-text").input_value().startswith("sfen ")
        page.locator("#output-format").select_option("kif")
        with page.expect_download() as event:
            page.locator("#download-output").click()
        event.value.save_as("/tmp/shogi-ui-output.kif")
        page.screenshot(path=str(ROOT / "docs/ui-desktop.png"), full_page=True)
        # Any subsequent edit invalidates exported text but export stays available.
        page.locator("#board .square").nth(40).click()
        expect(page.locator("#output-area")).to_be_hidden()
        expect(page.locator("#export")).to_be_enabled()
        # Preserve hand input even when its confirmation is still pending.
        page.locator("#hands-b input[data-piece=R]").fill("1")
        with page.expect_download() as event:
            page.locator("#save-draft").click()
        event.value.save_as("/tmp/shogi-ui-draft.json")
        page.locator(".tools > summary").click()
        page.locator("#draft-file").set_input_files("/tmp/shogi-ui-draft.json")
        expect(page.locator("#hands-b input[data-piece=R]")).to_have_value("1")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(path=str(ROOT / "docs/ui-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print(
        "Browser flow passed: upload → recognize → edit/undo → review → KIF download; mobile overflow check passed"
    )


if __name__ == "__main__":
    main()
