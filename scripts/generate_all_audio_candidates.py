#!/usr/bin/env python3
"""Synthesize six *unreviewed* draft narrations from verified author manuscripts.

Outputs stay in a separate workflow artifact, never in site/ or media/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


# Pin the exact model and voice pack used for the verified six-essay drafts.
# Hashes come from the successful Actions model-provenance record.
KOKORO_MODEL_SHA256 = "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a"
KOKORO_VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"


def verify_model_assets(model: Path, voices: Path) -> None:
    """Fail closed if either downloaded release artifact differs from its pin."""
    for file, expected in ((model, KOKORO_MODEL_SHA256), (voices, KOKORO_VOICES_SHA256)):
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"Missing or unsafe Kokoro asset: {file.name}")
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"Kokoro release-asset checksum mismatch: {file.name}")



def segments_for(text: str, max_chars: int = 850) -> list[tuple[str, bool]]:
    """Return source-faithful speech chunks and paragraph-break markers."""
    from generate_narration_candidate import text_chunks

    paragraphs = [p.strip() for p in text.strip().split("\n\n")]
    if not paragraphs or any(not p for p in paragraphs):
        raise ValueError("Narration contains an empty paragraph")
    result: list[tuple[str, bool]] = []
    for paragraph in paragraphs:
        chunks = text_chunks(paragraph, max_chars)
        for index, chunk in enumerate(chunks):
            result.append((chunk, index == len(chunks) - 1))
    if " ".join(chunk for chunk, _ in result) != " ".join(text.split()):
        raise ValueError("Narration chunks fail exact normalized-text reconstruction")
    return result


def timeline_for_lengths(
    segments: list[tuple[str, bool]],
    frame_lengths: list[int],
    sample_rate: int,
) -> tuple[list[dict], int]:
    """Map every unchanged source phrase to its actual synthesized time range.

    Times refer to pre-encoding PCM. MP3 encoder delay introduces minor offsets;
    these are approximate review cues, not word-aligned timestamps.
    """
    if len(segments) != len(frame_lengths) or not segments or sample_rate <= 0:
        raise ValueError("Audio segment lengths and speech phrases must agree")
    timeline = []
    cursor = 0
    paragraph = 1
    for index, ((text, paragraph_end), length) in enumerate(zip(segments, frame_lengths, strict=True)):
        if length <= 0:
            raise ValueError("Speech segments must contain positive audio frames")
        start = cursor
        cursor += length
        pause_seconds = 0.0 if index == len(segments) - 1 else (0.42 if paragraph_end else 0.18)
        timeline.append({
            "segment": index + 1,
            "paragraph": paragraph,
            "start_seconds": round(start / sample_rate, 3),
            "end_seconds": round(cursor / sample_rate, 3),
            "pause_after_seconds": pause_seconds,
            "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_excerpt": text[:100],
        })
        if paragraph_end:
            paragraph += 1
        cursor += int(sample_rate * pause_seconds)
    return timeline, cursor


def encode_audio(wav: Path, mp3: Path, sample_rate: int) -> None:
    """Normalize source WAV once to -18 LUFS, encode MP3, then fully decode."""
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
         "-i", str(wav),
         "-af", "loudnorm=I=-18:TP=-1.5:LRA=9",
         "-ar", str(sample_rate), "-codec:a", "libmp3lame", "-b:a", "96k", str(mp3)],
        capture_output=True, text=True, timeout=600,
    )
    if completed.returncode:
        raise RuntimeError(f"Mastering failed for {mp3.name}: {completed.stderr[-300:]}")
    checked = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-i", str(mp3), "-map", "0:a:0", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    if checked.returncode:
        raise RuntimeError(f"MP3 decoding failed for {mp3.name}: {checked.stderr[-300:]}")


def measure_audio(mp3: Path) -> dict:
    """Independently verify draft loudness, true peak and excessive silence."""
    output = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(mp3),
         "-af", "silencedetect=noise=-38dB:d=2.5,"
                "loudnorm=I=-18:TP=-1.5:LRA=9:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=600,
    )
    if output.returncode:
        raise ValueError(f"Audio measurement failed: {mp3.name}")
    match = re.search(r'\{\s*"input_i"[\s\S]*?\}', output.stderr)
    if match is None:
        raise ValueError(f"No integrated loudness measurement: {mp3.name}")
    data = json.loads(match.group())
    lufs = float(data["input_i"])
    true_peak = float(data["input_tp"])
    if not -20 <= lufs <= -16:
        raise ValueError(f"Integrated loudness outside review range: {mp3.name}: {lufs} LUFS")
    if true_peak > -1.0:
        raise ValueError(f"True peak exceeds -1 dBTP: {mp3.name}: {true_peak}")
    long_pauses = [
        float(value) for value in re.findall(r"silence_duration:\s*([0-9.]+)", output.stderr)
        if float(value) >= 2.5
    ]
    if long_pauses:
        raise ValueError(f"Excessive silence in {mp3.name}: {long_pauses[:4]}")
    return {
        "integrated_lufs": lufs,
        "true_peak_dbtp": true_peak,
        "loudness_range_lu": float(data["input_lra"]),
        "silences_over_2_5_seconds": 0,
        "mastering_target": "-18 LUFS, true peak <= -1.5 dBTP",
    }


def generate(root: Path, model: Path, voices: Path, output: Path,
             voice: str, limit: int, speed: float = 1.0) -> dict:
    from generate_narration_candidate import validated_speed
    speed = validated_speed(speed)
    from prepare_narration import compile_narration
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    verify_model_assets(model, voices)
    output.mkdir(parents=True, exist_ok=True)
    manifest = compile_narration(root, output / "manuscripts")
    kokoro = Kokoro(str(model), str(voices))
    results = []
    for essay in manifest["essays"]:
        slug = essay["slug"]
        source = (output / "manuscripts" / f"{slug}.txt").read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == essay["spoken_body_sha256"]
        segments = segments_for(source, limit)
        audio_segments = []
        sample_rate = None
        for index, (text, paragraph_end) in enumerate(segments):
            samples, rate = kokoro.create(text, voice=voice, speed=speed, lang="en-us")
            samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            if samples.size == 0 or not np.isfinite(samples).all():
                raise ValueError(f"Unusable model output in {slug} segment {index + 1}")
            if sample_rate is None:
                sample_rate = rate
            if rate != sample_rate:
                raise ValueError(f"Sample rate changed during {slug}")
            audio_segments.append(samples)
        timeline, expected_frames = timeline_for_lengths(
            segments, [part.size for part in audio_segments], sample_rate
        )
        buffer = []
        for part, item in zip(audio_segments, timeline, strict=True):
            buffer.append(part)
            pause = item["pause_after_seconds"]
            if pause:
                buffer.append(np.zeros(int(sample_rate * pause), dtype=np.float32))
        waveform = np.concatenate(buffer)
        if len(waveform) != expected_frames:
            raise AssertionError(f"Timeline length disagrees with audio: {slug}")
        wav = output / f"UNREVIEWED-{slug}.wav"
        mp3 = output / f"UNREVIEWED-{slug}.mp3"
        sf.write(wav, waveform, sample_rate, subtype="PCM_16")
        encode_audio(wav, mp3, sample_rate)
        wav.unlink()
        measurements = measure_audio(mp3)
        record = {
            "slug": slug, "title": essay["title"],
            "tts_speed": speed,
            "manuscript_sha256": essay["spoken_body_sha256"],
            "word_count": essay["word_count"],
            "chunks": len(segments),
            "segment_timeline": timeline,
            "signal_quality": measurements,
            "duration_seconds": round(len(waveform) / sample_rate, 2),
            "sha256": hashlib.sha256(mp3.read_bytes()).hexdigest(),
            "filename": mp3.name,
            "status": "UNREVIEWED_DRAFT",
            "reviewed": False,
            "approved_for_publication": False,
        }
        results.append(record)
        print(f"UNREVIEWED {slug}: {record['duration_seconds']} seconds, "
              f"{len(segments)} chunks", flush=True)

    report = {
        "project": "Forward Science",
        "status": "UNREVIEWED_SYNTHETIC_DRAFTS",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "voice": voice,
        "tts_speed": speed,
        "voice_provider": "Kokoro-82M / kokoro-onnx",
        "model": "Kokoro 82M v1.0 model-files-v1.1 (Apache-2.0)",
        "mastering": "FFmpeg single-pass from original PCM: -18 LUFS, -1.5 dBTP, 24kHz mono, 96kbps MP3",
        "inference": "onnxruntime local CPU",
        "recordings": results,
        "publication_approved": False,
        "reviewer": None,
        "license_source": "https://huggingface.co/hexgrad/Kokoro-82M",
    }
    (output / "UNREVIEWED-MANIFEST.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "READ-ME-FIRST.txt").write_text(
        "UNREVIEWED SYNTHETIC NARRATION CANDIDATES\n\n"
        "These MP3 files are test renders, not definitive editions.\n"
        "They were not approved through a full listening comparison.\n"
        "Check every sentence, scientific pronunciation, acoustics, and segment\n"
        "junction against the included manuscripts. Do not publish until human\n"
        "review and rights confirmation satisfy the public audio release gate.\n"
        "The GitHub Pages website is unchanged.\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--voices", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("narration-drafts"))
    p.add_argument("--voice", default="af_heart")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Neural synthesis speed (0.85–1.25; 1.10 for Michael)")
    p.add_argument("--max-chars", type=int, default=850)
    args = p.parse_args()
    generated = generate(args.root, args.model, args.voices, args.output,
                         args.voice, args.max_chars, args.speed)
    print(f"Prepared {len(generated['recordings'])} UNREVIEWED drafts only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
