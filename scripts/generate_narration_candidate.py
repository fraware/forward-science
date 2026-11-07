#!/usr/bin/env python3
"""Generate an *unreviewed* Kokoro narration sample for editorial voice testing.

This program never edits content/audio.json or the static site's public media.
Its output is a temporary candidate, subject to a human listening decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def validated_speed(value: float) -> float:
    """Keep neural synthesis in a modest, finite range suitable for prose.

    Speeds beyond this range deserve separate audio-quality review and are not
    silently accepted in the release-production pipeline.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Speech speed must be a finite number from 0.85 to 1.25")
    speed = float(value)
    if not math.isfinite(speed) or not 0.85 <= speed <= 1.25:
        raise ValueError("Speech speed must be a finite number from 0.85 to 1.25")
    return speed


def text_chunks(text: str, limit: int = 330) -> list[str]:
    """Partition normalized source text without changing or discarding words."""
    if limit < 80:
        raise ValueError("Chunk length must be at least 80")
    words = text.split()
    if not words:
        raise ValueError("Empty narration candidate")
    chunks: list[str] = []
    working: list[str] = []
    for word in words:
        if len(word) > limit:
            raise ValueError("A single source word exceeds the chunk limit")
        if working and len(" ".join(working + [word])) > limit:
            chunks.append(" ".join(working))
            working = []
        working.append(word)
        if len(" ".join(working)) >= limit * 0.6 and word.endswith((".", "?", "!")):
            chunks.append(" ".join(working))
            working = []
    if working:
        chunks.append(" ".join(working))
    if " ".join(chunks) != " ".join(words):
        raise AssertionError("Source-text chunk reconstruction failed")
    return chunks


def master_preview(wav: Path, mp3: Path, sample_rate: int) -> dict:
    """Normalize a preview to the approved-loudness target and verify it.

    Evenly mastered clips support a fair voice audition without implying that
    their pronunciation, intonation or completeness have been approved.
    """
    if sample_rate <= 0 or not wav.is_file():
        raise ValueError("Missing WAV source or invalid sample rate")
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
         "-i", str(wav), "-af", "loudnorm=I=-18:TP=-1.5:LRA=9",
         "-ar", str(sample_rate), "-ac", "1",
         "-codec:a", "libmp3lame", "-b:a", "96k", str(mp3)],
        capture_output=True, text=True, timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(f"MP3 mastering failed for {mp3.name}: {completed.stderr[-250:]}")
    from generate_all_audio_candidates import measure_audio
    return measure_audio(mp3)


def generate(root: Path, model: Path, voices: Path, output: Path,
             voice: str, speed: float = 1.0) -> dict:
    """Render a two-paragraph preview; publishable editions use a separate gate."""
    speed = validated_speed(speed)
    from prepare_narration import compile_narration
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    output.mkdir(parents=True, exist_ok=True)
    prepared = compile_narration(root, output / "manuscripts")
    essay = next(x for x in prepared["essays"] if x["slug"] == "forward-science")
    paragraphs = (output / "manuscripts/forward-science.txt").read_text(encoding="utf-8").split("\n\n")
    sample_text = " ".join(paragraphs[:2]).strip()
    pieces = text_chunks(sample_text)
    if not model.is_file() or not voices.is_file():
        raise FileNotFoundError("Pinned model and voice archives must be provided locally")
    tts = Kokoro(str(model), str(voices))
    waveforms = []
    sample_rate = None
    for index, piece in enumerate(pieces, 1):
        audio, rate = tts.create(piece, voice=voice, speed=speed, lang="en-us")
        if sample_rate is None:
            sample_rate = rate
        if rate != sample_rate or not np.asarray(audio).size:
            raise ValueError(f"Audio generation failed at segment {index}")
        waveforms.append(np.asarray(audio, dtype=np.float32).reshape(-1))
        waveforms.append(np.zeros(int(sample_rate * 0.24), dtype=np.float32))
    waveform = np.concatenate(waveforms)
    if not np.isfinite(waveform).all():
        raise ValueError("Model returned non-finite audio samples")
    wav = output / "UNREVIEWED-forward-science-preview.wav"
    mp3 = output / "UNREVIEWED-forward-science-preview.mp3"
    sf.write(wav, waveform, sample_rate, subtype="PCM_16")
    # Previous raw previews measured -24.5 to -27.9 LUFS. Use an
    # independent -18 LUFS measurement before comparing voice naturalness.
    signal_quality = master_preview(wav, mp3, sample_rate)
    wav.unlink()
    report = {
        "status": "CANDIDATE_ONLY_UNREVIEWED",
        "essay": "forward-science",
        "source_narration_sha256": essay["spoken_body_sha256"],
        "sample_text_sha256": hashlib.sha256(sample_text.encode()).hexdigest(),
        "sample_text": sample_text,
        "voice": voice,
        "tts_speed": speed,
        "model": "Kokoro-82M v1.0, ONNX model-files-v1.1",
        "provider": "Open-weight local inference using kokoro-onnx",
        "language": "en-us",
        "chunks": len(pieces),
        "duration_seconds": round(len(waveform) / sample_rate, 2),
        "signal_quality": signal_quality,
        "mastering": "FFmpeg loudnorm -18 LUFS target, -1.5 dBTP target; mono 96 kbps MP3",
        "mp3_sha256": hashlib.sha256(mp3.read_bytes()).hexdigest(),
        "editorial_review": "NOT_PERFORMED",
        "publication_approved": False,
        "license_sources": [
            "https://huggingface.co/hexgrad/Kokoro-82M",
            "https://github.com/thewh1teagle/kokoro-onnx",
        ],
    }
    (output / "CANDIDATE-NOT-FOR-PUBLICATION.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--voices", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("narration-candidate"))
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Neural synthesis speed (0.85–1.25; 1.10 for Michael)")
    args = parser.parse_args()
    report = generate(args.root, args.model, args.voices, args.output,
                      args.voice, args.speed)
    print(f"Candidate synthesized: {report['duration_seconds']} seconds, NOT approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
