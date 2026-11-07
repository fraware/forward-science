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


def test_unreviewed_audio_is_opt_in_with_native_controls():
    """A source-pinned recording appears only inside a closed listener disclosure."""
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from build import load_essays
    essays = load_essays(ROOT)
    essay = essays[0]
    sha = json.loads((ROOT / "content/audio-previews.json").read_text())[
        "recordings"
    ][essay["slug"]]["sha256"]
    essay.update({
        "audio": f"media/preview-{essay['slug']}.mp3",
        "audio_sha256": sha,
        "audio_preview": True,
        "audio_voice": {"type": "synthetic", "name": "Michael", "provider": "Kokoro-82M"},
    })
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    essay_html = env.get_template("essay.html.j2").render(
        essay=essay, essays=essays, previous=None, next=essays[1],
        base_url="https://example.org",
    )
    homepage = env.get_template("index.html.j2").render(
        essays=essays, base_url="https://example.org",
    )
    page = BeautifulSoup(essay_html, "html.parser")
    home = BeautifulSoup(homepage, "html.parser")
    assert page.select_one("article.prose") is not None
    disclosure = page.select_one("details#listen.listen-option")
    assert disclosure is not None and not disclosure.has_attr("open")
    assert disclosure.select_one("summary").get_text(" ", strip=True) == "Listen to this essay"
    assert disclosure.select_one(".listen-option__note") is None
    assert "Synthetic narration" not in page.get_text(" ", strip=True)
    audio = disclosure.select_one("audio[data-essay-audio][controls]")
    assert audio is not None
    assert audio["preload"] == "none"
    assert not audio.has_attr("autoplay")
    assert audio["src"] == f"../media/preview-{essay['slug']}.mp3?v={sha[:12]}"
    assert page.select_one(".audio-edition, .resume-reading") is None
    assert home.select_one(".essay__metadata, #continue-reading") is None
    assert home.select_one(f'a[href="{essay["slug"]}/#listen"]') is None
    assert not any(
        text in essay_html for text in ("AI preview", "AI narration by Michael")
    )


def test_media_check_rejects_corrupt_mp3(tmp_path):
    file = tmp_path / "broken.mp3"
    file.write_bytes(b"InvalidMP3" * 200)
    with pytest.raises(ValueError, match="inspect preview MP3"):
        preview.media_check(file, 500)
