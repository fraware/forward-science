"""Structural tests for the generated static publication."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build.py"
spec = importlib.util.spec_from_file_location("forward_science_build", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_six_articles_and_canonical_metadata() -> None:
    essays = module.load_essays(ROOT)
    assert len(essays) == 6
    assert essays[0]["slug"] == "forward-science"
    assert essays[-1]["slug"] == "future-laboratory"
    assert [e["number"] for e in essays] == [f"{i:02d}" for i in range(6)]
    assert essays[1]["date"] > essays[2]["date"]  # declared order differs from publication dates
    assert essays[0]["date_long"] == "June 22, 2026"


def preview_root(tmp_path: Path) -> Path:
    """Construct a source checkout with metadata but no imported articles."""
    root = tmp_path / "unimported"
    (root / "content").mkdir(parents=True)
    (root / "templates").mkdir()
    (root / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    for template in (ROOT / "templates").iterdir():
        (root / "templates" / template.name).write_bytes(template.read_bytes())
    for asset in ("styles.css", "favicon.svg", "reader.js"):
        (root / asset).write_bytes((ROOT / asset).read_bytes())
    (root / "content" / "landmarks.json").write_bytes((ROOT / "content" / "landmarks.json").read_bytes())
    (root / "content" / "audio.json").write_bytes((ROOT / "content" / "audio.json").read_bytes())
    return root


def test_preview_build_has_no_false_full_text_claims(tmp_path: Path) -> None:
    root = preview_root(tmp_path)
    out = tmp_path / "site"
    module.build(root, out, None)
    home = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert len(home.select("ol.essay-list > li")) == 6
    assert home.select_one("h1").get_text(" ", strip=True) == "Forward Science"
    for essay in module.load_essays(root):
        page = out / essay["slug"] / "index.html"
        assert page.is_file()
        parsed = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert parsed.select_one('meta[name="robots"]')["content"] == "noindex,follow"
        assert parsed.select_one('link[rel="canonical"]')["href"] == essay["original_url"]
        assert parsed.select_one('a.source-action')["href"] == essay["original_url"]
        assert not parsed.select_one('article[aria-label="Full essay"]')
    assert not (out / "sitemap.xml").exists()


def test_strict_fails_until_all_originals_are_present(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="incomplete chapters"):
        module.build(preview_root(tmp_path), tmp_path / "strict", "https://example.org", strict=True)


def test_strict_build_accepts_full_verified_export(tmp_path: Path) -> None:
    essays = module.build(ROOT, tmp_path / "full", "https://example.org", strict=True)
    assert len(essays) == 6
    assert all(essay["complete"] for essay in essays)
    for essay in essays:
        page = BeautifulSoup((tmp_path / "full" / essay["slug"] / "index.html").read_text(), "html.parser")
        assert page.select_one('article[aria-label="Full essay"]')
        assert not page.select_one('meta[name="robots"]')
        assert page.select_one('link[rel="canonical"]')["href"] == f"https://example.org/{essay['slug']}/"


def test_base_url_validation() -> None:
    assert module.verify_base_url("https://example.org/site/") == "https://example.org/site"
    for value in ("http://example.org", "//example.org", "https://example.org/x/../y", "https://example.org/?a=1", "https://user:pass@example.org"):
        with pytest.raises(ValueError):
            module.verify_base_url(value)


def test_no_broken_local_routes(tmp_path: Path) -> None:
    out = tmp_path / "site"
    module.build(ROOT, out, None)
    for page in out.rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.find_all("a", href=True):
            url = link["href"].split("#", 1)[0]
            if not url or url.startswith(("http://", "https://", "mailto:")):
                continue
            local = (page.parent / url)
            resolved = local / "index.html" if local.is_dir() else local
            assert resolved.is_file(), f"Broken link in {page}: {link['href']}"


def test_published_pages_preserve_source_and_omit_export_footer(tmp_path: Path) -> None:
    """Keep the Substack export immutable while excluding its subscription widget."""
    essays = module.build(ROOT, tmp_path / "published", "https://example.org/forward-science", strict=True)
    for essay in essays:
        assert essay["body"].strip().endswith(module.SUBSTACK_SUBSCRIBE_FOOTER)
        assert "Subscribe now" not in essay["display_body"]
        page = BeautifulSoup(
            (tmp_path / "published" / essay["slug"] / "index.html").read_text(encoding="utf-8"),
            "html.parser",
        )
        assert "Subscribe now" not in page.get_text(" ", strip=True)
        canonical = page.select_one('link[rel="canonical"]')["href"]
        assert page.select_one('meta[property="og:url"]')["content"] == canonical
        assert page.select_one('meta[property="og:site_name"]')["content"] == "Forward Science"
        if essay["number"] == "00":
            assert page.title.string == "Forward Science — Mateo H. Petel"

def test_landmark_navigation_is_semantically_valid(tmp_path: Path) -> None:
    """Curated destinations must match real paragraphs without altering source."""
    essays = module.build(ROOT, tmp_path / "landmark-build", "https://example.org", strict=True)
    for essay in essays:
        page = BeautifulSoup(
            (tmp_path / "landmark-build" / essay["slug"] / "index.html").read_text(),
            "html.parser",
        )
        anchors = page.select(".reader-toc nav a")
        assert 3 <= len(anchors) <= 7
        assert len(anchors) == len(essay["landmarks"])
        for anchor in anchors:
            dest = anchor["href"][1:]
            assert page.select_one(f"article p[id='{dest}']") is not None
        assert page.select_one("script[src='../reader.js']") is not None
        assert (tmp_path / "landmark-build" / "reader.js").is_file()


def test_audio_is_not_advertised_without_recordings(tmp_path: Path) -> None:
    """Audio playback appears exclusively when a verified asset is present."""
    module.build(ROOT, tmp_path / "no-audio", "https://example.org", strict=True)
    for essay in module.load_essays(ROOT):
        text = (tmp_path / "no-audio" / essay["slug"] / "index.html").read_text()
        assert 'class="audio-edition"' not in text
        assert "<audio " not in text


def test_audio_manifest_validates_files_and_sha256(tmp_path: Path) -> None:
    """Only a checksum-verified recording may appear in the public player."""
    import hashlib
    import json
    import shutil

    source = tmp_path / "source"
    shutil.copytree(ROOT / "content", source / "content")
    shutil.copytree(ROOT / "templates", source / "templates")
    for asset in ("styles.css", "favicon.svg", "reader.js"):
        shutil.copy2(ROOT / asset, source / asset)
    slug = "scientific-loop"
    media = source / "media" / f"{slug}.mp3"
    media.parent.mkdir()
    # The fixture deliberately uses inert bytes; it validates the release gate,
    # not MP3 decoding or listening quality.
    data = b"sample-audio-fixture"
    media.write_bytes(data)
    manifest = {slug: {
        "path": f"media/{slug}.mp3",
        "sha256": hashlib.sha256(data).hexdigest(),
        "voice": {"type": "synthetic", "name": "af_heart", "provider": "Kokoro-82M"},
    }}
    (source / "content" / "audio.json").write_text(json.dumps(manifest), encoding="utf-8")
    site = tmp_path / "site"
    # A synthetic byte sequence exercises only the existing path/hash gate.
    # Strict builds must reject it as an unreviewed or undecodable recording.
    module.build(source, site, None, strict=False)
    with pytest.raises(ValueError, match="Suspicious MP3 size|listening review"):
        module.build(source, tmp_path / "unreviewed", None, strict=True)
    page = BeautifulSoup((site / slug / "index.html").read_text(), "html.parser")
    disclosure = page.select_one("details#listen.listen-option")
    assert disclosure is not None and not disclosure.has_attr("open")
    assert disclosure.select_one("summary").get_text(strip=True) == "Listen to this essay"
    player = disclosure.select_one("audio[data-essay-audio]")
    assert player is not None and player["preload"] == "none"
    assert player.has_attr("controls") and not player.has_attr("autoplay")
    assert player["src"] == "../media/scientific-loop.mp3?v=" + hashlib.sha256(data).hexdigest()[:12]
    assert "AI preview" not in page.get_text(" ", strip=True)
    assert (site / "media" / f"{slug}.mp3").read_bytes() == data
    media.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Audio checksum mismatch"):
        module.build(source, tmp_path / "invalid", None, strict=False)


def test_public_site_has_no_offline_downloads(tmp_path: Path) -> None:
    """Public pages and deployment artifacts never expose offline editions."""
    import shutil

    output = tmp_path / "site"
    legacy = output / "downloads"
    legacy.mkdir(parents=True)
    (legacy / "forward-science.pdf").write_bytes(b"old-version")
    essays = module.build(ROOT, output, "https://example.org/forward-science", strict=True)
    assert len(essays) == 6
    assert not legacy.exists()
    for page in output.rglob("*.html"):
        content = page.read_text(encoding="utf-8")
        assert "Read offline" not in content
        assert "Complete collection" not in content
        assert "downloads/forward-science." not in content
        soup = BeautifulSoup(content, "html.parser")
        assert not soup.select(".download-editions, .chapter-download")


def test_no_browser_tts_or_copy_citation_in_published_essays(tmp_path: Path) -> None:
    """Only independently reviewed audio may expose public playback controls."""
    out = tmp_path / "voice-free"
    module.build(ROOT, out, "https://example.org/site", strict=True)
    assert not (out / "device-narration.js").exists()
    javascript = (out / "reader.js").read_text(encoding="utf-8")
    assert "copy-citation" not in javascript
    assert "Citation copied" not in javascript
    for essay in module.load_essays(ROOT):
        page = BeautifulSoup((out / essay["slug"] / "index.html").read_text(), "html.parser")
        assert page.select_one('script[src="../device-narration.js"]') is None
        assert page.select_one("[data-device-narration]") is None
        assert page.select_one("[data-speech-play]") is None
        assert page.select_one(".copy-citation") is None
        assert page.select_one(".reader-status") is None
        assert "Copy citation" not in page.get_text(" ", strip=True)
        assert page.select_one('article[aria-label="Full essay"]') is not None
        assert page.select_one("audio") is None
        assert page.select_one(".resume-reading") is None


def test_incremental_build_removes_legacy_speech_asset(tmp_path: Path) -> None:
    """Rebuilding into an old site must retract previously shipped system TTS."""
    out = tmp_path / "old-site"
    module.build(ROOT, out, "https://example.org/site", strict=True)
    old = out / "device-narration.js"
    old.write_text("/* no longer published */", encoding="utf-8")
    module.build(ROOT, out, "https://example.org/site", strict=True)
    assert not old.exists()


def test_strict_build_retracts_removed_audio(tmp_path: Path) -> None:
    """A revoked recording is removed from a reused site's published assets."""
    output = tmp_path / "site"
    stale = output / "media" / "scientific-loop.mp3"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old unreviewed recording")
    module.build(ROOT, output, "https://example.org/forward-science", strict=True)
    assert not stale.exists()
    assert not (output / "media").exists()


def test_strict_build_rejects_unknown_assets(tmp_path: Path) -> None:
    """Private files accidentally placed under site/ fail closed before upload."""
    output = tmp_path / "site"
    output.mkdir()
    (output / "PRIVATE-notes.json").write_text('{"subscriber": "private"}')
    with pytest.raises(ValueError, match="Unexpected file in public publication"):
        module.build(ROOT, output, "https://example.org/forward-science", strict=True)


def test_build_refuses_overlapping_source_paths(tmp_path: Path) -> None:
    """A mistaken output argument must never mutate authoritative sources."""
    with pytest.raises(ValueError, match="overlaps publication sources"):
        module.build(ROOT, ROOT / "content", None, strict=False)
    with pytest.raises(ValueError, match="overlaps publication sources"):
        module.build(ROOT, ROOT, None, strict=False)


@pytest.mark.parametrize(
    "relative_output",
    ["docs", "tests", "browser", ".github", "site/alternate"],
)
def test_build_rejects_other_repository_destinations(relative_output: str) -> None:
    """Do not overwrite project files even if the destination is not a known source root."""
    with pytest.raises(ValueError, match="overlaps publication sources"):
        module.build(ROOT, ROOT / relative_output, None, strict=False)


def test_build_rejects_symlinked_output_root(tmp_path: Path) -> None:
    """A redirected generated root must not affect an external directory."""
    external = tmp_path / "external"
    external.mkdir()
    output = tmp_path / "site"
    output.symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="Generated output path is a symlink"):
        module.build(ROOT, output, None, strict=False)
    assert list(external.iterdir()) == []


def test_build_rejects_symlinked_chapter_before_rendering(tmp_path: Path) -> None:
    """Check existing output paths before any chapter write follows a symlink."""
    output = tmp_path / "site"
    external = tmp_path / "external"
    output.mkdir()
    external.mkdir()
    (output / "forward-science").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink forbidden in generated publication"):
        module.build(ROOT, output, None, strict=False)
    assert list(external.iterdir()) == []


def test_build_refuses_symlinked_media_output(tmp_path: Path) -> None:
    """Build cleanup must never follow a preexisting publication media symlink."""
    output = tmp_path / "site"
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.mp3").write_bytes(b"keep")
    output.mkdir()
    (output / "media").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="media path is a symlink"):
        module.build(ROOT, output, None, strict=True)
    assert (external / "keep.mp3").read_bytes() == b"keep"


def test_editorial_typography_has_no_remote_font_dependency() -> None:
    """Use a readable, stable book face without tracking or CDN font requests."""
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    assert '"Palatino Linotype"' in css
    assert 'Baskerville' in css
    assert '--display:' in css
    assert 'font: 20px/1.7 var(--serif)' in css
    assert 'overflow-wrap: break-word' in css
    assert '.hero { padding-block:' in css
    for forbidden in ('@import', '@font-face', 'fonts.googleapis', 'fonts.gstatic'):
        assert forbidden not in css
    homepage = (ROOT / "templates/index.html.j2").read_text(encoding="utf-8")
    assert '<h1 id="page-title">Forward Science</h1>' in homepage
    assert 'FORWARD SCIENCE<span' not in homepage
    assert 'A series in six parts' not in homepage
    for template in ("index.html.j2", "essay.html.j2"):
        html = (ROOT / "templates" / template).read_text(encoding="utf-8")
        assert 'name="theme-color" content="#faf9f6"' in html
        assert 'http://fonts.' not in html and 'https://fonts.' not in html


def test_series_register_and_colophon_are_consistent_across_seven_pages(tmp_path: Path) -> None:
    """Every part has a meaningful link and one current-page marker on its page."""
    site = tmp_path / "monograph"
    essays = module.build(ROOT, site, "https://example.org/forward-science", strict=True)
    assert [e["chapter_roman"] for e in essays] == ["I", "II", "III", "IV", "V", "VI"]
    home = BeautifulSoup((site / "index.html").read_text(), "html.parser")
    home_links = home.select('nav.chapter-register[aria-label="The six parts of Forward Science"] ol a')
    assert len(home_links) == 6
    assert not any(a.has_attr("aria-current") for a in home_links)
    assert [a["href"] for a in home_links] == [e["slug"] + "/" for e in essays]
    assert [a["aria-label"] for a in home_links] == [
        f'Part {e["chapter_roman"]}. {e["title"]}' for e in essays
    ]
    assert [a.get_text(strip=True) for a in home_links] == [
        e["chapter_roman"] for e in essays
    ]
    contents = home.select("ol.essay-list > li")
    assert [entry["id"] for entry in contents] == [
        f'part-{e["chapter_roman"]}' for e in essays
    ]
    assert [entry.select_one(".essay__number").get_text(strip=True) for entry in contents] == [
        e["chapter_roman"] for e in essays
    ]
    assert home.select_one("#colophon-title").get_text(strip=True) == "Colophon"
    assert home.select_one('#about a[href="https://mateopetel.substack.com/t/forward-science"]')
    assert not home.select_one(".closing")
    for essay in essays:
        page = BeautifulSoup((site / essay["slug"] / "index.html").read_text(), "html.parser")
        links = page.select('nav.chapter-register[aria-label="The six parts of Forward Science"] ol a')
        assert len(links) == 6
        assert [a["href"] for a in links] == [f'../{e["slug"]}/' for e in essays]
        assert [a.get_text(strip=True) for a in links] == [
            e["chapter_roman"] for e in essays
        ]
        current = [a for a in links if a.get("aria-current") == "page"]
        assert len(current) == 1
        assert current[0]["href"] == f'../{essay["slug"]}/'
        assert page.select_one(".chapter-kicker").get_text(" ", strip=True).startswith(
            f'Part {essay["chapter_roman"]}'
        )
        assert page.select_one('article[aria-label="Full essay"]')


def test_public_homepage_omits_progress_and_essay_action_metadata(tmp_path: Path) -> None:
    """The six chapter titles, not utility links or timestamps, organize the index."""
    out = tmp_path / "clean-home"
    essays = module.build(ROOT, out, "https://example.org/forward-science", strict=True)
    home = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    entries = home.select("ol.essay-list > li")
    assert len(entries) == 6
    assert [e.select_one("h3 a")["href"] for e in entries] == [
        essay["slug"] + "/" for essay in essays
    ]
    assert all(len(e.select("a")) == 1 for e in entries)
    assert all(not e.select("time, .essay__metadata") for e in entries)
    assert not home.select_one("#continue-reading, #clear-reading-progress")
    assert not home.select_one('script[src="reader.js"]')
    assert "Pick up where you left off" not in home.get_text(" ", strip=True)
    assert "Listen (preview)" not in home.get_text(" ", strip=True)
    for essay in essays:
        page = BeautifulSoup(
            (out / essay["slug"] / "index.html").read_text(encoding="utf-8"),
            "html.parser",
        )
        assert page.select_one("article.prose") is not None
        assert page.select_one("#listen, .audio-edition, audio, .resume-reading") is None
    assert not (out / "media").exists()
