"""No-network, no-charge tests of the optional ElevenLabs narrator audition."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "elevenlabs_audition", ROOT / "scripts" / "generate_elevenlabs_audition.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"


def test_preview_is_free_and_bound_to_original_verified_text(tmp_path: Path):
    calls = []
    def forbidden(*_args):
        calls.append(True)
        raise AssertionError("dry-run initiated an API charge")

    report = module.audition(ROOT, tmp_path / "preview", VOICE_ID, False,
                             transport=forbidden)
    assert calls == []
    assert report["status"] == "NO_CHARGE_PREVIEW"
    assert report["publication_approved"] is False
    assert report["estimated_credits"] == report["sample_characters"]
    assert report["sample_characters"] > 300
    assert len(report["manuscript_sha256"]) == 64
    assert len(report["sample_text_sha256"]) == 64
    assert (tmp_path / "preview" / module.OUTPUT_NAME).exists() is False
    persisted = json.loads((tmp_path / "preview" / "AUDITION-UNREVIEWED.json").read_text())
    assert persisted == report


def test_paid_audition_requires_key_credit_ceiling_and_explicit_voice(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-for-tests-only")
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError("API called despite missing authorization")
    with pytest.raises(ValueError, match="requires an explicitly selected voice ID"):
        module.audition(ROOT, tmp_path / "missing", None, True, 5000, transport=forbidden)
    with pytest.raises(ValueError, match="Estimated charge exceeds"):
        module.audition(ROOT, tmp_path / "cost", VOICE_ID, True, 1, transport=forbidden)
    with pytest.raises(ValueError, match="valid ElevenLabs"):
        module.audition(ROOT, tmp_path / "invalid", "not an id!", True,
                        5000, transport=forbidden)
    assert not calls


def test_paid_audition_one_request_is_private_and_unapproved(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-for-tests-only")
    requests = []
    audio = b"ID3" + b"\0" * 40_000

    def transport(voice_id, text, key):
        requests.append((voice_id, text, key))
        return audio

    def validator(path):
        assert path.read_bytes() == audio
        return 57.0

    out = tmp_path / "a-private-audition"
    report = module.audition(ROOT, out, VOICE_ID, True, 5000,
                             transport=transport, validator=validator)
    assert len(requests) == 1
    assert requests[0][0] == VOICE_ID
    assert requests[0][2] == "secret-for-tests-only"
    assert len(requests[0][1]) == report["sample_characters"]
    assert (out / module.OUTPUT_NAME).read_bytes() == audio
    assert report["status"] == "UNREVIEWED_AUDIO"
    assert report["publication_approved"] is False
    assert report["full_listening_review"] is False
    assert report["distribution_rights_confirmed"] is False
    raw = (out / "AUDITION-UNREVIEWED.json").read_text()
    assert "secret-for-tests-only" not in raw
    with pytest.raises(ValueError, match="duplicate paid generation"):
        module.audition(ROOT, out, VOICE_ID, True, 5000,
                        transport=transport, validator=validator)
    assert len(requests) == 1


def test_missing_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Missing ELEVENLABS_API_KEY"):
        module.audition(ROOT, tmp_path / "key", VOICE_ID, True, 5000,
                        transport=lambda *_: (_ for _ in ()).throw(
                            AssertionError("should never call API")))


@pytest.mark.parametrize("target", [
    "site/narration", "content/media", "media/unapproved", ".github/audio",
    "docs/audio", "templates/media", "scripts/audio", "tests/media",
])
def test_private_audio_cannot_write_inside_authority_directories(target):
    with pytest.raises(ValueError, match="overlap project authority"):
        module.safe_output(ROOT, ROOT / target)


def test_audio_output_requires_bounded_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-for-tests-only")
    with pytest.raises(ValueError, match="bounded MP3"):
        module.audition(ROOT, tmp_path / "bad-response", VOICE_ID, True, 5000,
                        transport=lambda *_: b"not an mp3")
    assert not (tmp_path / "bad-response" / module.OUTPUT_NAME).exists()


def test_sample_matches_kokoro_candidate_exactly():
    """The paid/free comparison uses the same two author-export paragraphs."""
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    import hashlib
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        root = Path(directory)
        metadata = compile_narration(ROOT, root)
        text = (root / "forward-science.txt").read_text(encoding="utf-8")
        expected = " ".join(text.split("\n\n")[:2]).strip()
        sample, entire_hash = module.verified_sample(ROOT)
        assert sample == expected
        assert entire_hash == metadata["essays"][0]["spoken_body_sha256"]
        assert hashlib.sha256(sample.encode()).hexdigest()
