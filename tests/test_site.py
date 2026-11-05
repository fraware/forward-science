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
    for asset in ("styles.css", "favicon.svg", "reader.js", "device-narration.js"):
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
    for asset in ("styles.css", "favicon.svg", "reader.js", "device-narration.js"):
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
    assert page.select_one("audio[src='../media/scientific-loop.mp3']") is not None
    description = page.select_one(".audio-edition__description")
    assert description is not None
    assert "Synthetic narration" in description.get_text(" ", strip=True)
    assert "af_heart" in description.get_text(" ", strip=True)
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


def test_browser_narration_is_progressively_enhanced(tmp_path: Path) -> None:
    """The browser-voice option is opt-in and separate from reviewed recordings."""
    out = tmp_path / "spoken"
    module.build(ROOT, out, "https://example.org/site", strict=True)
    assert (out / "device-narration.js").is_file()
    for essay in module.load_essays(ROOT):
        page = BeautifulSoup((out / essay["slug"] / "index.html").read_text(), "html.parser")
        assert page.select_one('script[src="../device-narration.js"]') is not None
        assert page.select_one('[data-device-narration][hidden]') is not None
        assert page.select_one('[data-speech-play]') is not None
        assert page.select_one('[data-speech-status][role="status"]') is not None
        assert page.select_one('article[aria-label="Full essay"]') is not None


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
