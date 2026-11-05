"""Audio publication checks use synthetic bytes and mocked codec tools in CI."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_audio", ROOT / "scripts/verify_audio.py")
assert spec and spec.loader
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
SLUG = "scientific-loop"


def fixture(tmp_path):
    work = tmp_path / "publication"
    shutil.copytree(ROOT / "content", work / "content")
    media = work / "media"
    media.mkdir()
    data = b"TEST-MP3-BYTES-ONLY" * 4000
    (media / f"{SLUG}.mp3").write_bytes(data)
    digest, words = v.manuscript_digest(work, SLUG)
    record = {
        "path": f"media/{SLUG}.mp3",
        "sha256": hashlib.sha256(data).hexdigest(),
        "manuscript_sha256": digest,
        "voice": {"type": "synthetic", "name": "Test Voice",
                  "provider": "Fake fixture", "distribution_rights_basis": "TEST ONLY"},
        "review": {"reviewer": "Test Reviewer", "reviewed_on": date.today().isoformat(),
                   **{flag: True for flag in v.REVIEW_FLAGS}},
    }
    (work / "content/audio.json").write_text(json.dumps({SLUG: record}))
    return work, record, words


def metadata(words):
    return {"streams": [{"codec_type": "audio", "codec_name": "mp3",
                         "channels": 1, "sample_rate": "44100", "bit_rate": "96000"}],
            "format": {"duration": str(words * 60 / 145)}}


def test_empty_manifest_passes_without_media_tools():
    assert v.validate(ROOT) == []


def test_verified_record_passes_with_mocked_probe(tmp_path):
    work, record, words = fixture(tmp_path)
    results = v.validate(work, inspect=lambda _: metadata(words), fully_decode=lambda _: None, acoustic=lambda _: {"integrated_lufs": -18.0, "true_peak_dbtp": -1.5, "silence_over_4_seconds": False})
    assert [x["slug"] for x in results] == [SLUG]


@pytest.mark.parametrize("corruption", ["audio", "script", "review", "rights"])
def test_fails_closed_for_unreviewed_or_changed_media(tmp_path, corruption):
    work, record, words = fixture(tmp_path)
    if corruption == "audio":
        (work / "media" / f"{SLUG}.mp3").write_bytes(b"broken")
    elif corruption == "script":
        record["manuscript_sha256"] = "f" * 64
    elif corruption == "review":
        record["review"]["listened_in_full"] = False
    else:
        record["voice"]["distribution_rights_basis"] = ""
    (work / "content/audio.json").write_text(json.dumps({SLUG: record}))
    with pytest.raises(ValueError):
        v.validate(work, inspect=lambda _: metadata(words), fully_decode=lambda _: None, acoustic=lambda _: {"integrated_lufs": -18.0, "true_peak_dbtp": -1.5, "silence_over_4_seconds": False})


def test_bad_codec_and_implausible_duration_rejected(tmp_path):
    work, _, words = fixture(tmp_path)
    broken = metadata(words)
    broken["streams"][0]["codec_name"] = "aac"
    with pytest.raises(ValueError, match="one MP3"):
        v.validate(work, inspect=lambda _: broken, fully_decode=lambda _: None, acoustic=lambda _: {"integrated_lufs": -18.0, "true_peak_dbtp": -1.5, "silence_over_4_seconds": False})
    too_fast = metadata(words)
    too_fast["format"]["duration"] = "2"
    with pytest.raises(ValueError, match="Implausible"):
        v.validate(work, inspect=lambda _: too_fast, fully_decode=lambda _: None, acoustic=lambda _: {"integrated_lufs": -18.0, "true_peak_dbtp": -1.5, "silence_over_4_seconds": False})


def test_digest_matches_production_narration_manuscript(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    manifest = compile_narration(ROOT, tmp_path / "narration")
    item = next(x for x in manifest["essays"] if x["slug"] == SLUG)
    digest, words = v.manuscript_digest(ROOT, SLUG)
    assert item["spoken_body_sha256"] == digest
    assert item["word_count"] == words


def test_ffmpeg_probe_and_decode_a_real_mp3_fixture(tmp_path):
    """Exercise the actual media toolchain, without pretending it is narration."""
    import subprocess
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.fail("FFmpeg and FFprobe must be available for audio release validation")
    path = tmp_path / "synthetic-tone.mp3"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
           "sine=frequency=440:duration=2", "-ar", "24000", "-ac", "1",
           "-af", "loudnorm=I=-18:TP=-1.5:LRA=9",
           "-codec:a", "libmp3lame", "-b:a", "64k", str(path)]
    completed = subprocess.run(cmd, capture_output=True, timeout=30)
    if completed.returncode != 0:
        pytest.fail("Runner lacks an MP3 encoder required for the real media test")
    info = v.probe(path)
    assert info["streams"][0]["codec_name"] == "mp3"
    assert 1.9 <= float(info["format"]["duration"]) <= 2.2
    v.decode(path)
    acoustic = v.measure_loudness(path)
    assert -21 <= acoustic["integrated_lufs"] <= -15
    assert acoustic["true_peak_dbtp"] <= -1


def test_release_rejects_out_of_range_audio_levels(tmp_path):
    """Attested review does not override an objectively defective audio master."""
    work, _, words = fixture(tmp_path)
    for metrics, message in [
        ({"integrated_lufs": -26, "true_peak_dbtp": -4, "silence_over_4_seconds": False}, "LUFS"),
        ({"integrated_lufs": -18, "true_peak_dbtp": -0.2, "silence_over_4_seconds": False}, "peak"),
        ({"integrated_lufs": -18, "true_peak_dbtp": -2, "silence_over_4_seconds": True}, "silence"),
    ]:
        with pytest.raises(ValueError, match=message):
            v.validate(
                work, inspect=lambda _: metadata(words), fully_decode=lambda _: None,
                acoustic=lambda _, report=metrics: report,
            )
