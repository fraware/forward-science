"""Candidate TTS chunking preserves source wording without depending on a model."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "candidate_narration", ROOT / "scripts/generate_narration_candidate.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("limit", [100, 180, 330])
def test_chunking_preserves_all_words_and_order(limit):
    text = "The scientific loop advances through a question, experiment, and review. " * 50
    chunks = module.text_chunks(text, limit)
    assert len(chunks) > 2
    assert all(0 < len(p) <= limit for p in chunks)
    assert " ".join(chunks) == " ".join(text.split())


def test_chunking_fails_on_unrepresentable_input():
    with pytest.raises(ValueError):
        module.text_chunks(" ")
    with pytest.raises(ValueError):
        module.text_chunks("a" * 100, limit=80)


def test_narration_candidate_uses_verified_source_text(tmp_path):
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    manifest = compile_narration(ROOT, tmp_path / "manuscripts")
    original = next(e for e in manifest["essays"] if e["slug"] == "forward-science")
    assert original["segments"]
    text = (tmp_path / "manuscripts/forward-science.txt").read_text(encoding="utf-8")
    sample = " ".join(text.split("\n\n")[:2]).strip()
    chunks = module.text_chunks(sample)
    assert " ".join(chunks) == " ".join(sample.split())


def test_candidate_mastering_meets_signal_target_with_real_ffmpeg(tmp_path):
    """A voice audition must be loudness comparable before subjective scoring."""
    import shutil
    import subprocess
    import sys

    assert shutil.which("ffmpeg"), "FFmpeg is required in the audio CI runner"
    sys.path.insert(0, str(ROOT / "scripts"))
    wav = tmp_path / "synthetic.wav"
    mp3 = tmp_path / "normalized.mp3"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-ar", "24000", "-ac", "1", "-y", str(wav)],
        check=True, timeout=35,
    )
    quality = module.master_preview(wav, mp3, 24000)
    assert mp3.stat().st_size > 15000
    assert -20 <= quality["integrated_lufs"] <= -16
    assert quality["true_peak_dbtp"] <= -1
    assert quality["silences_over_2_5_seconds"] == 0


def test_candidate_mastering_rejects_bad_input(tmp_path):
    with pytest.raises(ValueError, match="Missing WAV source or invalid sample rate"):
        module.master_preview(tmp_path / "missing.wav", tmp_path / "out.mp3", 24000)


@pytest.mark.parametrize("speed", [0.85, 1.0, 1.10, 1.25])
def test_narration_speed_accepts_bounded_neural_rate(speed):
    assert module.validated_speed(speed) == speed


@pytest.mark.parametrize("speed", [0.0, -1.0, 0.849, 1.251, 20, float("nan"), float("inf"), -float("inf"), None, True])
def test_narration_speed_rejects_invalid_rates(speed):
    with pytest.raises(ValueError, match="finite number"):
        module.validated_speed(speed)


def test_default_and_selected_speed_are_independent_of_text_segmentation():
    text = "Long-form scientific prose should retain exact phrasing. " * 15
    chunks = module.text_chunks(text)
    assert " ".join(chunks) == " ".join(text.split())
    assert module.validated_speed(1.10) == 1.10
