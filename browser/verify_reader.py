"""Real Chromium integration checks for Forward Science's static reader.

Runs in an isolated GitHub Actions job, using a loopback HTTP server. Browser
audio previews and approved editions use native controls; no browser voice fallback.
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



def test_optional_audio_disclosure_and_direct_listening_link(server_url, browser):
    """A reading-only visit leaves audio closed; an explicit choice reveals controls."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(server_url + "/scientific-loop/", wait_until="load")

    # The local browser build contains no published MP3, so exercise the same
    # progressive disclosure with an inert media element and real reader.js.
    page.evaluate("""() => {
      const details = document.createElement('details');
      details.id = 'listen';
      details.className = 'audio-edition';
      details.innerHTML = '<summary>Listen to this essay</summary>' +
        '<div class="audio-edition__content">' +
        '<audio controls preload="none" data-audio-for="scientific-loop" ' +
        'data-audio-sha="' + 'a'.repeat(64) + '"></audio></div>';
      document.querySelector('.reading-tools').appendChild(details);
    }""")
    page.evaluate("""() => new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '../reader.js?optional-disclosure-test=1';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    })""")
    assert page.locator("details#listen").evaluate("(element) => element.open") is False
    assert page.locator("details#listen audio").get_attribute("preload") == "none"
    assert page.locator("details#listen audio").evaluate("(audio) => audio.paused") is True

    page.locator("#listen > summary").click()
    page.wait_for_function("() => document.querySelector('#listen audio').preload === 'metadata'")
    assert page.locator("details#listen").evaluate("(element) => element.open") is True
    page.locator("#listen > summary").click()
    assert page.locator("details#listen").evaluate("(element) => element.open") is False

    # The homepage Listen link uses #listen. It expands the player without autoplay.
    page.evaluate("() => { location.hash = '#listen'; }")
    page.wait_for_function("() => document.querySelector('#listen').open")
    assert page.locator("#listen audio").evaluate("(audio) => audio.paused") is True
    context.close()


def test_audio_resume_skip_rate_and_completion_with_injected_media(server_url, browser):
    """The public manifest stays empty; synthetic audio exists only inside Chromium."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/scientific-loop/")
    observed = page.evaluate("""async () => {
      const slug = 'scientific-loop', sha = 'a'.repeat(64);
      const key = 'forward-science:audio:v1:' + slug;
      localStorage.setItem(key, JSON.stringify({sha256: sha, time: 75}));
      const holder = document.createElement('section');
      const audio = document.createElement('audio');
      audio.dataset.audioFor = slug;
      audio.dataset.audioSha = sha;
      holder.append(audio);
      const controls = {};
      for (const [kind, name] of [
          ['back', 'audio-skip-back'], ['forward', 'audio-skip-forward'],
          ['resume', 'audio-resume']]) {
        const button = document.createElement('button');
        button.className = name;
        button.disabled = kind !== 'resume';
        button.hidden = kind === 'resume';
        holder.append(button);
        controls[kind] = button;
      }
      const speed = document.createElement('select');
      speed.className = 'audio-speed';
      for (const rate of ['1', '1.25']) {
        const option = document.createElement('option');
        option.value = rate;
        option.textContent = rate;
        speed.append(option);
      }
      holder.append(speed);
      const feedback = document.createElement('p');
      feedback.className = 'audio-feedback';
      holder.append(feedback);
      document.querySelector('.reading-tools').append(holder);
      let clock = 0, played = 0;
      Object.defineProperty(audio, 'duration', {get: () => 240});
      Object.defineProperty(audio, 'currentTime', {
        get: () => clock, set: value => { clock = value; }
      });
      audio.play = () => {
        played++;
        audio.dispatchEvent(new Event('play'));
        return Promise.resolve();
      };
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.onload = resolve;
        script.onerror = reject;
        script.src = '../reader.js?integration-audio=1';
        document.body.append(script);
      });
      audio.dispatchEvent(new Event('loadedmetadata'));
      // Chrome may fire these during media initialization even if untouched.
      audio.dispatchEvent(new Event('timeupdate'));
      audio.dispatchEvent(new Event('pause'));
      window.dispatchEvent(new Event('pagehide'));
      const idleBookmark = JSON.parse(localStorage.getItem(key));
      const prompt = controls.resume.textContent;
      const noAutoplay = played === 0 && clock === 0;
      controls.resume.click();
      const resumed = clock, playCount = played;
      controls.back.click();
      const rewound = clock;
      controls.forward.click();
      const forwarded = clock;
      speed.value = '1.25';
      speed.dispatchEvent(new Event('change'));
      audio.dispatchEvent(new Event('pause'));
      const saved = JSON.parse(localStorage.getItem(key));
      audio.dispatchEvent(new Event('ended'));
      const completed = JSON.parse(localStorage.getItem(key));
      window.dispatchEvent(new Event('pagehide')); // Must not undo completed state.
      const completedAfterExit = JSON.parse(localStorage.getItem(key));
      return {prompt, noAutoplay, idleBookmark, resumed, playCount, rewound, forwarded,
        playbackRate: audio.playbackRate, saved, completed, completedAfterExit,
        preference: localStorage.getItem('forward-science:audio-rate:v1'),
        resumeHidden: controls.resume.hidden};
    }""")
    assert observed["prompt"] == "Resume at 1:15"
    assert observed["idleBookmark"] == {"sha256": "a" * 64, "time": 75}
    assert observed["noAutoplay"] is True
    assert observed["resumed"] == 75
    assert observed["playCount"] == 1
    assert observed["rewound"] == 60
    assert observed["forwarded"] == 90
    assert observed["saved"] == {"sha256": "a" * 64, "time": 90}
    assert observed["completed"] == {"sha256": "a" * 64, "time": 0}
    assert observed["completedAfterExit"] == observed["completed"]
    assert observed["playbackRate"] == 1.25
    assert observed["preference"] == "1.25"
    assert observed["resumeHidden"] is True
    context.close()


def test_unplayed_audio_pagehide_never_creates_a_bookmark(server_url, browser):
    """Background visits must leave the visitor's audio storage empty."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/forward-science/")
    result = page.evaluate("""async () => {
      const key = 'forward-science:audio:v1:forward-science';
      localStorage.removeItem(key);
      const audio = document.createElement('audio');
      audio.dataset.audioFor = 'forward-science';
      audio.dataset.audioSha = 'c'.repeat(64);
      document.querySelector('.reading-tools').append(audio);
      Object.defineProperty(audio, 'duration', {get: () => 180});
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.onload = resolve;
        script.onerror = reject;
        script.src = '../reader.js?integration-audio=idle';
        document.body.append(script);
      });
      audio.dispatchEvent(new Event('loadedmetadata'));
      audio.dispatchEvent(new Event('timeupdate'));
      audio.dispatchEvent(new Event('pause'));
      window.dispatchEvent(new Event('pagehide'));
      return localStorage.getItem(key);
    }""")
    assert result is None
    context.close()


def test_native_scrub_saves_only_after_user_seeks(server_url, browser):
    """A visitor can bookmark a deliberate native-player seek before playback."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/scientific-loop/")
    result = page.evaluate("""async () => {
      const key = 'forward-science:audio:v1:scientific-loop';
      localStorage.setItem(key, JSON.stringify({sha256:'d'.repeat(64), time:75}));
      const audio = document.createElement('audio');
      audio.dataset.audioFor = 'scientific-loop';
      audio.dataset.audioSha = 'd'.repeat(64);
      document.querySelector('.reading-tools').append(audio);
      let time = 0;
      Object.defineProperty(audio, 'duration', {get: () => 240});
      Object.defineProperty(audio, 'currentTime', {
        get: () => time, set: value => {time = value;}
      });
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.onload = resolve;
        script.onerror = reject;
        script.src = '../reader.js?integration-audio=scrub';
        document.body.append(script);
      });
      audio.dispatchEvent(new Event('loadedmetadata'));
      audio.currentTime = 120;
      audio.dispatchEvent(new Event('seeked'));
      const afterSeek = JSON.parse(localStorage.getItem(key));
      window.dispatchEvent(new Event('pagehide'));
      const afterExit = JSON.parse(localStorage.getItem(key));
      return {afterSeek, afterExit};
    }""")
    assert result["afterSeek"] == {"sha256": "d" * 64, "time": 120}
    assert result["afterExit"] == result["afterSeek"]
    context.close()


def test_audio_resume_rejects_old_edition_checksum(server_url, browser):
    """A replacement recording never inherits the earlier edition's bookmark."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(server_url + "/forward-science/")
    result = page.evaluate("""async () => {
      const key = 'forward-science:audio:v1:forward-science';
      localStorage.setItem(key, JSON.stringify({sha256: 'a'.repeat(64), time: 225}));
      const holder = document.createElement('div');
      const audio = document.createElement('audio');
      audio.dataset.audioFor = 'forward-science';
      audio.dataset.audioSha = 'b'.repeat(64);
      holder.append(audio);
      const resume = document.createElement('button');
      resume.className = 'audio-resume';
      resume.hidden = true;
      holder.append(resume);
      document.querySelector('.reading-tools').append(holder);
      Object.defineProperty(audio, 'duration', {get: () => 300});
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.onload = resolve;
        script.onerror = reject;
        script.src = '../reader.js?integration-audio=2';
        document.body.append(script);
      });
      audio.dispatchEvent(new Event('loadedmetadata'));
      return {hidden: resume.hidden, time: audio.currentTime};
    }""")
    assert result == {"hidden": True, "time": 0}
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
