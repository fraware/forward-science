"""Real Chromium integration checks for Forward Science's static reader.

Runs in an isolated GitHub Actions job, using a loopback HTTP server. Browser
only reviewed audio editions appear; no browser voice fallback is shipped.
"""
from __future__ import annotations

import functools
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
KEY = "forward-science:reading:v1"
SLUGS = (
    "forward-science", "forward-deployed-scientists", "scientific-loop",
    "extension-agents", "political-economy", "future-laboratory",
)


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    site = tmp_path_factory.mktemp("reader-browser") / "site"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build.py"), "--strict",
         "--base-url", "https://fraware.github.io/forward-science",
         "--out", str(site)],
        check=True, cwd=ROOT, timeout=40, capture_output=True, text=True,
    )
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(site))
    http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}"
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            yield chromium
        finally:
            chromium.close()


def test_all_pages_at_four_viewports(server_url, browser):
    """Real navigation checks both layout and the no-download editorial policy."""
    for width, height in [(320, 720), (390, 844), (768, 1024), (1440, 900)]:
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        for slug in ("", *SLUGS):
            route = f"/{slug}/" if slug else "/"
            response = page.goto(server_url + route, wait_until="load")
            assert response is not None and response.status == 200
            assert page.locator("h1").count() == 1
            assert "Read offline" not in page.locator("body").inner_text()
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            assert overflow <= 1, f"Horizontal overflow on {route} at {width}px: {overflow}"
            if slug:
                assert page.locator("article.prose p[id]").count() >= 10
                assert page.locator(".reader-toc nav a").count() >= 3
        context.close()


def test_real_navigation_and_paragraph_links(server_url, browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/")
    assert page.locator("ol.essay-list > li").count() == 6
    page.locator(".essay-list h3 a").first.click()
    assert page.url.endswith("/forward-science/")
    page.locator(".reader-toc summary").click()
    anchor = page.locator(".reader-toc nav a").nth(2)
    target = anchor.get_attribute("href")
    anchor.click()
    assert page.evaluate("location.hash") == target
    assert page.locator(target).count() == 1
    page.locator(".chapter-navigation__next").click()
    assert page.url.endswith("/forward-deployed-scientists/")
    context.close()


def test_saved_resume_survives_initial_render_on_tall_screen(server_url, browser):
    """Initial viewport intersection must never silently replace saved location."""
    context = browser.new_context(viewport={"width": 1280, "height": 2200})
    page = context.new_page()
    page.goto(server_url + "/")
    page.evaluate(
        """key => localStorage.setItem(key, JSON.stringify({
            slug: 'forward-science', paragraph: 'p-10',
            title: 'Forward Science', updated: 1700000000
        }))""", KEY
    )
    page.goto(server_url + "/forward-science/")
    assert page.locator(".resume-reading").is_visible()
    page.wait_for_timeout(150)
    stored = page.evaluate("key => JSON.parse(localStorage.getItem(key))", KEY)
    assert stored["paragraph"] == "p-10"
    start_scroll = page.evaluate("window.scrollY")
    page.locator(".resume-reading").click()
    assert not page.locator(".resume-reading").is_visible()
    page.wait_for_function(
        """before => {
           const p = document.querySelector('#p-10');
           if (!p) return false;
           const bounds = p.getBoundingClientRect();
           return window.scrollY > before + 5 &&
                  bounds.bottom > 0 && bounds.top < innerHeight;
        }""",
        arg=start_scroll,
        timeout=5000,
    )
    context.close()


def test_home_continue_and_clear_are_local(server_url, browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/")
    page.evaluate(
        """key => localStorage.setItem(key, JSON.stringify({
             slug: 'scientific-loop', paragraph: 'p-09', title: 'The Scientific Loop'
         }))""", KEY
    )
    page.reload()
    link = page.locator("#continue-reading-link")
    assert link.is_visible()
    assert link.get_attribute("href") == "scientific-loop/#p-09"
    page.locator("#clear-reading-progress").click()
    assert not page.locator("#continue-reading").is_visible()
    assert page.evaluate("key => localStorage.getItem(key)", KEY) is None
    context.close()


def test_no_browser_voice_or_copy_citation_even_if_supported(server_url, browser):
    """No site-owned Web Speech or clipboard controls may appear in an essay."""
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script("""() => {
      Object.defineProperty(window, 'speechSynthesis', {
        configurable: true,
        value: { speak() { throw Error('speech synthesis must not run'); } }
      });
    }""")
    for slug in SLUGS:
        page.goto(server_url + f"/{slug}/")
        assert page.locator(".copy-citation").count() == 0
        assert page.locator(".reader-status").count() == 0
        assert page.locator("[data-device-narration]").count() == 0
        assert page.locator("[data-speech-play]").count() == 0
        assert page.locator('script[src*="device-narration"]').count() == 0
        assert page.locator("audio").count() == 0
        assert page.locator("article.prose p").count() >= 10
    context.close()


def test_no_javascript_still_has_text_and_navigation(server_url, browser):
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(server_url + "/extension-agents/")
    assert page.locator("article.prose p").count() >= 10
    assert page.locator(".reader-toc nav a").count() >= 3
    page.locator(".chapter-navigation__next").click()
    assert page.url.endswith("/political-economy/")
    context.close()
