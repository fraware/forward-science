"""Public listening previews are explicit, source-pinned and never approved audio."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_audio_previews", ROOT / "scripts/verify_audio_previews.py"
)
assert spec and spec.loader
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def test_preview_manifest_is_exact_six_and_explicitly_unreviewed():
    pins = json.loads((ROOT / "content/audio-previews.json").read_text())
    essays = json.loads((ROOT / "content/essays.json").read_text())
    assert set(pins["recordings"]) == {entry["slug"] for entry in essays}
    assert pins["status"] == "PUBLIC_PREVIEW_UNREVIEWED"
    assert pins["publication_approved"] is False
    assert pins["voice"] == "am_michael"
    assert pins["tts_speed"] == 1.10
    assert pins["artifact_run_id"] == 42388856204
    for key, value in pins["recordings"].items():
        assert len(value["sha256"]) == 64, key
        assert len(value["manuscript_sha256"]) == 64, key
    # Final editions remain a wholly independent, human-reviewed decision.
    assert json.loads((ROOT / "content/audio.json").read_text()) == {}


def test_previews_refused_without_exact_private_media(tmp_path):
    with pytest.raises(ValueError, match="Missing or unsafe"):
        preview.validate(ROOT, tmp_path / "nonexistent")
    folder = tmp_path / "media"
    folder.mkdir()
    with pytest.raises(ValueError, match="Missing private production receipt"):
        preview.validate(ROOT, folder)
    (folder / "UNREVIEWED-MANIFEST.json").write_text("{}")
    with pytest.raises(ValueError, match="receipt hash differs"):
        preview.validate(ROOT, folder)


def test_preview_render_shows_honest_status_native_controls_and_no_autoplay():
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from build import load_essays
    essays = load_essays(ROOT)
    essay = essays[0]
    sha = json.loads((ROOT / "content/audio-previews.json").read_text())["recordings"][essay["slug"]]["sha256"]
    essay.update({
        "audio": f"media/preview-{essay['slug']}.mp3",
        "audio_sha256": sha,
        "audio_preview": True,
        "audio_voice": {"type":"synthetic", "name":"Michael", "provider":"Kokoro-82M"},
    })
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("essay.html.j2").render(
        essay=essay, previous=None, next=essays[1], base_url="https://example.org",
    )
    page = BeautifulSoup(html, "html.parser")
    title = page.select_one("#listen .audio-edition__title")
    assert title and "Preview" in title.get_text()
    description = page.select_one("#listen .audio-edition__description").get_text(" ", strip=True)
    assert "AI narration by Michael" in description
    assert "not yet received full editorial listening review" in description
    player = page.select_one("#listen audio[data-audio-for]")
    assert player["src"] == f"../media/preview-{essay['slug']}.mp3?v={sha[:12]}"
    assert player["data-audio-sha"] == sha
    assert player.has_attr("controls")
    assert not player.has_attr("autoplay")
    assert page.select_one(".audio-skip-back") is not None
    assert page.select_one(".audio-skip-forward") is not None
    assert page.select_one(".audio-resume") is not None
    assert page.select_one(".audio-speed") is not None
    assert page.select_one('article[aria-label="Full essay"]') is not None
    home = env.get_template("index.html.j2").render(essays=essays, base_url="https://example.org")
    homepage = BeautifulSoup(home, "html.parser")
    link = homepage.select_one(f'a[href="{essay["slug"]}/#listen"]')
    assert link and "preview" in link.get_text().lower()


def test_media_check_rejects_corrupt_mp3(tmp_path):
    file = tmp_path / "broken.mp3"
    file.write_bytes(b"InvalidMP3" * 200)
    with pytest.raises(ValueError, match="inspect preview MP3"):
        preview.media_check(file, 500)
