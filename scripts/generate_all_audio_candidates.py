#!/usr/bin/env python3
"""Synthesize six *unreviewed* draft narrations from verified author manuscripts.

Outputs stay in a separate workflow artifact, never in site/ or media/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path



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


def encode_audio(wav: Path, mp3: Path) -> None:
    """Produce a browser-compatible draft MP3, then fully decode for integrity."""
    completed = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
         "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "96k", str(mp3)],
        capture_output=True, text=True, timeout=180,
    )
    if completed.returncode:
        raise RuntimeError(f"Encoding failed for {mp3.name}: {completed.stderr[-300:]}")
    checked = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-i", str(mp3), "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    if checked.returncode:
        raise RuntimeError(f"MP3 decoding failed for {mp3.name}: {checked.stderr[-300:]}")


def generate(root: Path, model: Path, voices: Path, output: Path, voice: str, limit: int) -> dict:
    from prepare_narration import compile_narration
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    if not model.is_file() or not voices.is_file():
        raise FileNotFoundError("The official ONNX model and voice tensors must be available")
    output.mkdir(parents=True, exist_ok=True)
    manifest = compile_narration(root, output / "manuscripts")
    kokoro = Kokoro(str(model), str(voices))
    results = []
    for essay in manifest["essays"]:
        slug = essay["slug"]
        source = (output / "manuscripts" / f"{slug}.txt").read_text(encoding="utf-8")
        assert hashlib.sha256(source.encode()).hexdigest() == essay["spoken_body_sha256"]
        segments = segments_for(source, limit)
        buffer = []
        sample_rate = None
        for index, (text, paragraph_end) in enumerate(segments):
            samples, rate = kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
            samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            if samples.size == 0 or not np.isfinite(samples).all():
                raise ValueError(f"Unusable model output in {slug} segment {index + 1}")
            if sample_rate is None:
                sample_rate = rate
            if rate != sample_rate:
                raise ValueError(f"Sample rate changed during {slug}")
            buffer.append(samples)
            if index + 1 < len(segments):
                seconds = 0.42 if paragraph_end else 0.18
                buffer.append(np.zeros(int(rate * seconds), dtype=np.float32))
        waveform = np.concatenate(buffer)
        wav = output / f"UNREVIEWED-{slug}.wav"
        mp3 = output / f"UNREVIEWED-{slug}.mp3"
        sf.write(wav, waveform, sample_rate, subtype="PCM_16")
        encode_audio(wav, mp3)
        wav.unlink()
        record = {
            "slug": slug, "title": essay["title"],
            "manuscript_sha256": essay["spoken_body_sha256"],
            "word_count": essay["word_count"],
            "chunks": len(segments),
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
        "voice_provider": "Kokoro-82M / kokoro-onnx",
        "model": "Kokoro 82M v1.0 model-files-v1.1 (Apache-2.0)",
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
    p.add_argument("--max-chars", type=int, default=850)
    args = p.parse_args()
    generated = generate(args.root, args.model, args.voices, args.output,
                         args.voice, args.max_chars)
    print(f"Prepared {len(generated['recordings'])} UNREVIEWED drafts only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
