"""Network-free tests for private, blinded, source-faithful voice auditions."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "blind_audition", ROOT / "scripts" / "build_blind_voice_review.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_inputs(tmp_path: Path) -> Path:
    """Write simple fake MP3 bytes; this suite tests identity and packaging."""
    src = tmp_path / "candidates"
    sample = "One verified paragraph. Another original paragraph."
    sample_hash = hashlib.sha256(sample.encode("utf-8")).hexdigest()
    for voice in module.VOICES:
        directory = src / voice
        directory.mkdir(parents=True)
        media = directory / module.CLIP_NAME
        data = b"ID3" + voice.encode() + b"test-only-bytes"
        media.write_bytes(data)
        receipt = {
            "voice": voice,
            "essay": "forward-science",
            "mp3_sha256": hashlib.sha256(data).hexdigest(),
            "source_narration_sha256": "1" * 64,
            "sample_text_sha256": sample_hash,
            "sample_text": sample,
            "publication_approved": False,
        }
        (directory / module.METADATA_NAME).write_text(
            json.dumps(receipt), encoding="utf-8")
    return src


def acceptable(_path: Path) -> dict:
    """Stub only audio signal measurement; source/byte checks still run."""
    return {"integrated_lufs": -18.1, "true_peak_dbtp": -2}


def test_all_four_equal_source_private_clips_are_anonymized(tmp_path):
    src = fixture_inputs(tmp_path)
    out = tmp_path / "private-listening"
    result = module.build(src, out, measurement=acceptable)
    assert result["status"] == "UNREVIEWED_AUDITIONS"
    assert result["publication_approved"] is False
    assert len(result["audio_sha256"]) == 4
    key = json.loads((out / "VOICE-KEY-OPEN-AFTER-LISTENING.json").read_text())
    assert len(key["mapping"]) == 4
    assert {item["voice"] for item in key["mapping"]} == set(module.VOICES)
    assert {item["letter"] for item in key["mapping"]} == set("ABCD")
    html = (out / "LISTEN-OFFLINE.html").read_text(encoding="utf-8")
    for voice in module.VOICES:
        assert voice not in html
    assert "http://" not in html and "https://" not in html
    assert 'src="Voice_A.mp3"' in html
    assert "publication_approved:false" in html
    assert "URL.createObjectURL" in html
    for item in key["mapping"]:
        recorded = out / f"Voice_{item['letter']}.mp3"
        assert recorded.read_bytes() == (src / item["voice"] / module.CLIP_NAME).read_bytes()


def test_tampered_clip_refused_without_output(tmp_path):
    source = fixture_inputs(tmp_path)
    (source / "bf_emma" / module.CLIP_NAME).write_bytes(b"tampered")
    out = tmp_path / "destination"
    with pytest.raises(ValueError, match="audio checksum"):
        module.build(source, out, measurement=acceptable)
    assert not out.exists()


def test_nonidentical_spoken_text_refused(tmp_path):
    source = fixture_inputs(tmp_path)
    receipt = source / "am_michael" / module.METADATA_NAME
    data = json.loads(receipt.read_text())
    data["sample_text"] = "A genuinely different passage."
    data["sample_text_sha256"] = hashlib.sha256(data["sample_text"].encode()).hexdigest()
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="different text"):
        module.build(source, tmp_path / "out", measurement=acceptable)


def test_underpowered_quiet_audio_rejected(tmp_path):
    source = fixture_inputs(tmp_path)
    with pytest.raises(ValueError, match="audition volume"):
        module.build(
            source, tmp_path / "out",
            measurement=lambda _: {"integrated_lufs": -27, "true_peak_dbtp": -5}
        )


def test_private_output_cannot_overlap_public_site_or_source(tmp_path):
    source = fixture_inputs(tmp_path)
    with pytest.raises(ValueError, match="overlaps source"):
        module.build(source, source / "af_heart" / "blind", measurement=acceptable)
    with pytest.raises(ValueError, match="overlaps source"):
        module.build(source, source, measurement=acceptable)


def test_existing_nonempty_destination_refused(tmp_path):
    source = fixture_inputs(tmp_path)
    out = tmp_path / "private-listening"
    out.mkdir()
    (out / "unrelated").write_text("old artifact")
    with pytest.raises(ValueError, match="new empty"):
        module.build(source, out, measurement=acceptable)


def test_unsafe_html_in_source_is_escaped():
    html = module.listening_html('<img src=x onerror="alert(1)">')
    assert "&lt;img" in html
    assert '<img src=x' not in html
    assert "http://" not in html
