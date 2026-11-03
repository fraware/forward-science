#!/usr/bin/env python3
"""Capture responsive previews and fail on horizontal page overflow.

Requires Playwright Python and an installed Chromium browser. Does not run in
GitHub Actions by default; optional development/visual QA utility.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--out", type=Path, default=ROOT / "previews")
    parser.add_argument("--browser", help="Optional path to Chromium; otherwise use Playwright-managed Chromium")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    views = [("desktop", 1440, 900), ("tablet", 768, 1024), ("mobile", 390, 844), ("small-mobile", 320, 720)]
    css = (args.site / "styles.css").read_text(encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**({"executable_path": args.browser} if args.browser else {}), headless=True, args=["--no-sandbox"])
        for label, width, height in views:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            for target, filename in [("index.html", "home"), ("future-laboratory/index.html", "chapter")]:
                # Navigation to file:// may be restricted in sandboxed browsers.
                # Set the generated markup and the exact local CSS directly.
                page.set_content((args.site / target).read_text(encoding="utf-8"), wait_until="load")
                page.add_style_tag(content=css)
                page.screenshot(path=str(args.out / f"{filename}-{label}.png"), full_page=True)
                metrics = page.evaluate("""() => ({width: document.documentElement.scrollWidth, viewport: window.innerWidth, title: document.title})""")
                if metrics["width"] > width:
                    raise SystemExit(f"Horizontal overflow in {target} at {width}px: {metrics}")
                print(f"PASS {target} {width}px: {metrics['title']}")
            page.close()
        browser.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
