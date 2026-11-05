"""Full-series candidate audio segmentation must preserve every source word."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "full_audio_candidate", ROOT / "scripts/generate_all_audio_candidates.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_segments_respect_paragraph_order_and_text_integrity(tmp_path):
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    compiled = compile_narration(ROOT, tmp_path / "narration")
    assert len(compiled["essays"]) == 6
    for essay in compiled["essays"]:
        text = (tmp_path / "narration" / f"{essay['slug']}.txt").read_text(encoding="utf-8")
        parts = module.segments_for(text, 850)
        assert all(0 < len(t) <= 850 for t, _ in parts)
        assert " ".join(p for p, _ in parts) == " ".join(text.split())
        assert sum(end for _, end in parts) == len(text.strip().split("\n\n"))
        assert len(parts) >= 1



def test_segment_timeline_covers_audio_and_respects_paragraphs():
    """Source phrase timing and intentional pauses are independently consistent."""
    segments = [
        ("First complete sentence.", False),
        ("Second phrase.", True),
        ("Last paragraph.", True),
    ]
    timeline, frames = module.timeline_for_lengths(segments, [24000, 48000, 24000], 24000)
    assert len(timeline) == 3
    assert frames == 24000 + 48000 + 24000 + int(0.18 * 24000) + int(0.42 * 24000)
    assert [x["paragraph"] for x in timeline] == [1, 1, 2]
    assert [x["pause_after_seconds"] for x in timeline] == [0.18, 0.42, 0]
    assert timeline[0]["start_seconds"] == 0
    assert timeline[1]["start_seconds"] == 1.18
    assert timeline[2]["end_seconds"] == round(frames / 24000, 3)
    assert timeline[0]["source_excerpt"] == "First complete sentence."
    import hashlib
    assert timeline[0]["source_sha256"] == hashlib.sha256(segments[0][0].encode()).hexdigest()


def test_segment_timeline_rejects_invalid_lengths():
    import pytest
    with pytest.raises(ValueError):
        module.timeline_for_lengths([("text", True)], [], 24000)
    with pytest.raises(ValueError):
        module.timeline_for_lengths([("text", True)], [0], 24000)
    with pytest.raises(ValueError):
        module.timeline_for_lengths([("text", True)], [100], 0)


def test_mastered_mp3_loudness_measured_with_real_ffmpeg(tmp_path):
    """Real media-toolchain check: loudness and long-silence gate."""
    import subprocess
    import shutil
    import pytest
    if not shutil.which("ffmpeg"):
        pytest.fail("ffmpeg is required for audio candidate validation")
    wav = tmp_path / "test.wav"
    mp3 = tmp_path / "test.mp3"
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2.5", "-ar", "24000", "-ac", "1",
        "-y", str(wav),
    ]
    subprocess.run(cmd, check=True, timeout=30)
    module.encode_audio(wav, mp3, 24000)
    measurement = module.measure_audio(mp3)
    assert -20 <= measurement["integrated_lufs"] <= -16
    assert measurement["true_peak_dbtp"] <= -1
