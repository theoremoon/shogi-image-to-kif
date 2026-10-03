"""Verify Pages under a subpath with a real WebAssembly runtime."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8770/site/")
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        errors, writes = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: (
                writes.append(request.url) if request.method == "POST" else None
            ),
        )
        page.goto(args.url)
        assert page.evaluate("Boolean(window.shogiBackend)")
        # Editor/export are usable without an image or a confirmation step.
        page.locator("#blank-board").click()
        page.locator("#export").click()
        expect(page.locator("#output-area")).to_be_visible(timeout=180000)
        page.locator("#copy-output").click()
        assert "先手番" in page.evaluate("navigator.clipboard.readText()")
        # Exercise sample loading under /repo/, not just localhost root.
        page.locator(".tools > summary").click()
        page.locator("#sample-list").select_option("commons-008")
        expect(page.locator("#source-canvas")).to_be_visible()
        page.locator("#recognize").click()
        expect(page.locator("#review-area")).to_be_visible(timeout=60000)
        expect(page.locator("#board .square")).to_have_count(81, timeout=60000)
        page.locator("#export").click()
        expect(page.locator("#output-area")).to_be_visible()
        # Optional local-only Wars fixture; never uploaded or added to site bundle.
        wars = ROOT / "data/local-samples/wars-mate.png"
        if wars.exists():
            page.locator("#image-file").set_input_files(wars)
            expect(page.locator("#review-area")).to_be_hidden()
            page.locator("#recognize").click()
            expect(page.locator("#review-area")).to_be_visible(timeout=60000)
            expect(page.locator("#board .square")).to_have_count(81, timeout=60000)
            expected = json.loads(
                (ROOT / "data/annotations/wars-mate.json").read_text()
            )["board"]
            draft = page.evaluate("draft")
            mismatches = [
                i for i, (a, b) in enumerate(zip(draft["board"], expected)) if a != b
            ]
            assert len(mismatches) <= 2, mismatches
            assert all(i in draft["review_squares"] for i in mismatches)
            page.locator("#export").click()
            expect(page.locator("#output-area")).to_be_visible()
            assert "金が5枚" in page.locator("#output-warnings").inner_text()
        assert not errors, errors
        assert not writes, writes
        browser.close()
    print(
        "Pages passed: subpath, WASM recognition, immediate export, clipboard, samples, Wars; zero POST requests"
    )


if __name__ == "__main__":
    main()
