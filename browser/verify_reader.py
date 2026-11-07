"""Real Chromium integration checks for Forward Science's static reader.

Runs in an isolated GitHub Actions job, using a loopback HTTP server. Browser
optional narration is closed by default; persistent reading history is absent.
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


def test_classic_editorial_typography_at_mobile_and_desktop(server_url, browser):
    """Reading measure and book-style hierarchy remain usable at all breakpoints."""
    for width, height in ((320, 720), (390, 844), (768, 1024), (1440, 900)):
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        response = page.goto(server_url + "/", wait_until="load")
        assert response is not None and response.status == 200
        home = page.evaluate("""() => {
          const style = (selector) => getComputedStyle(document.querySelector(selector));
          const heading = document.querySelector('.hero h1');
          return {
            title: heading.textContent.trim(),
            headingFont: style('.hero h1').fontFamily,
            bodyFont: style('body').fontFamily,
            headingAlign: style('.hero').textAlign,
            headingSize: parseFloat(style('.hero h1').fontSize),
            overflowing: document.documentElement.scrollWidth > window.innerWidth + 1,
            wordmark: document.querySelector('.wordmark').textContent.trim()
          };
        }""")
        assert home["title"] == "Forward Science"
        assert home["wordmark"] == "Forward Science"
        assert "Baskerville" in home["headingFont"]
        assert "Palatino Linotype" in home["bodyFont"]
        assert home["headingAlign"] == "left"
        assert home["headingSize"] >= 40
        assert home["overflowing"] is False

        page.goto(server_url + "/scientific-loop/", wait_until="load")
        essay = page.evaluate("""() => {
          const heading = getComputedStyle(document.querySelector('.chapter-heading'));
          const prose = document.querySelector('article.prose');
          const typography = getComputedStyle(prose);
          return {
            align: heading.textAlign,
            fontFamily: typography.fontFamily,
            fontSize: parseFloat(typography.fontSize),
            lineHeight: parseFloat(typography.lineHeight),
            measure: prose.getBoundingClientRect().width,
            overflowing: document.documentElement.scrollWidth > window.innerWidth + 1,
            controls: document.querySelectorAll('.reader-toc summary').length,
          };
        }""")
        assert essay["align"] == "left"
        assert "Palatino Linotype" in essay["fontFamily"]
        assert essay["fontSize"] >= 18
        assert 1.55 <= essay["lineHeight"] / essay["fontSize"] <= 1.8
        assert essay["measure"] <= 677
        assert essay["overflowing"] is False
        assert essay["controls"] == 1
        context.close()


def test_six_part_register_and_colophon_at_all_screen_widths(server_url, browser):
    """A six-part editorial index stays navigable and legible across devices."""
    for width, height in [(320, 720), (390, 844), (768, 1024), (1440, 900)]:
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.goto(server_url + "/", wait_until="load")
        register = page.locator('nav.chapter-register[aria-label="The six parts of Forward Science"]')
        assert register.locator("ol a").count() == 6
        assert [link.strip() for link in register.locator("ol a").all_text_contents()] == [
            "I", "II", "III", "IV", "V", "VI"
        ]
        assert register.locator('[aria-current="page"]').count() == 0
        assert page.locator("#colophon-title").inner_text() == "Colophon"
        assert page.locator("ol.essay-list > li").count() == 6
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
        )
        # Keyboard focus and anchors should work on every size, with no scripted navigation.
        register.locator("a").nth(2).click()
        assert page.url.endswith("/scientific-loop/")
        current = page.locator('nav.chapter-register a[aria-current="page"]')
        assert current.count() == 1
        assert current.inner_text().strip() == "III"
        assert current.get_attribute("aria-label").startswith("Part III.")
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
        )
        page.locator("nav.chapter-register a").last.click()
        assert page.url.endswith("/future-laboratory/")
        assert page.locator('nav.chapter-register a[aria-current="page"]').inner_text().strip() == "VI"
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


def test_public_pages_have_no_narration_history_or_per_essay_actions(server_url, browser):
    """The live presentation contains only titles and article navigation."""
    for width in (390, 1440):
        context = browser.new_context(viewport={"width": width, "height": 844})
        page = context.new_page()
        page.goto(server_url + "/")
        assert page.locator("ol.essay-list > li").count() == 6
        assert page.locator(".essay__metadata, #continue-reading, #continue-reading-link").count() == 0
        assert page.locator("ol.essay-list > li time").count() == 0
        assert page.locator("ol.essay-list > li a").count() == 6
        assert page.locator('script[src="reader.js"]').count() == 0
        assert "Listen (preview)" not in page.locator("body").inner_text()
        assert "Clear reading history" not in page.locator("body").inner_text()
        page.evaluate("""() => localStorage.setItem(
          'forward-science:reading:v1', JSON.stringify({
            slug: 'forward-science', paragraph: 'p-10'
          })
        )""")
        page.locator(".essay-list h3 a").first.click()
        assert page.url.endswith("/forward-science/")
        assert page.locator("#listen, audio, .audio-edition, .resume-reading").count() == 0
        assert page.locator(".reader-toc summary").count() == 1
        assert page.locator("article.prose p[id]").count() >= 10
        # Defer scripts may still be executing just after navigation.
        page.wait_for_function(
            "() => localStorage.getItem('forward-science:reading:v1') === null"
        )
        page.evaluate("""() => {
          document.documentElement.style.scrollBehavior = 'auto';
          const article = document.querySelector('article.prose');
          const top = article.getBoundingClientRect().top + window.scrollY;
          window.scrollTo({ top: top + article.offsetHeight / 2, behavior: 'instant' });
        }""")
        # Wait for the browser's scroll and animation frame, not an arbitrary delay.
        page.wait_for_function(
            "() => parseFloat(document.querySelector('.reading-progress span').style.width) > 0"
        )
        assert page.evaluate(
            "() => localStorage.getItem('forward-science:reading:v1')"
        ) is None
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



def test_optional_audio_player_is_closed_and_stops_when_collapsed(server_url, browser):
    """A reader explicitly opens the audio controls; closing stops narration."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(server_url + "/scientific-loop/", wait_until="load")
    page.evaluate("""() => {
      const details = document.createElement('details');
      details.id = 'listen';
      details.className = 'listen-option';
      details.innerHTML = '<summary>Listen to this essay</summary>' +
          '<div class="listen-option__body">' +
          '<audio controls preload="none" data-essay-audio></audio></div>';
      document.querySelector('.reading-tools').appendChild(details);
      const audio = details.querySelector('audio');
      window.__pauseCalls = 0;
      window.__playCalls = 0;
      Object.defineProperty(audio, 'paused', {get: () => false});
      audio.pause = () => { window.__pauseCalls += 1; };
      audio.play = () => { window.__playCalls += 1; return Promise.resolve(); };
    }""")
    page.evaluate("""() => new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '../reader.js?test=opt-in';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    })""")
    details = page.locator("details#listen")
    assert details.evaluate("(el) => el.open") is False
    assert page.locator("#listen audio").get_attribute("preload") == "none"
    assert page.evaluate("window.__playCalls") == 0
    page.locator("#listen > summary").click()
    page.wait_for_function(
        "() => document.querySelector('#listen audio').preload === 'metadata'"
    )
    assert details.evaluate("(el) => el.open") is True
    assert page.evaluate("window.__playCalls") == 0
    page.locator("#listen > summary").click()
    page.wait_for_function("() => window.__pauseCalls === 1")
    assert details.evaluate("(el) => el.open") is False
    page.evaluate("() => { location.hash = '#listen'; }")
    page.wait_for_function("() => document.querySelector('#listen').open")
    assert page.evaluate("window.__playCalls") == 0
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
