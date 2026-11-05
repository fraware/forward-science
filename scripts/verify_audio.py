#!/usr/bin/env python3
"""Verify provenance, technical decodability and attested review of published MP3s.

The review metadata attests human listening. These checks alone cannot
establish that spoken audio agrees with the written essay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

FOOTER = "https://mateopetel.substack.com/subscribe?"
REVIEW_FLAGS = ("listened_in_full", "spoken_text_checked",
                "pronunciation_checked", "audio_artifacts_checked",
                "distribution_rights_confirmed")


def manuscript_digest(root: Path, slug: str) -> tuple[str, int]:
    """Reconstruct the author-export narration manuscript, excluding the footer."""
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid essay identifier")
    soup = BeautifulSoup((root / "content/essays" / f"{slug}.html").read_text(), "html.parser")
    paragraphs = soup.find_all("p", recursive=False)
    if paragraphs and paragraphs[-1].find("a", href=FOOTER):
        paragraphs.pop()
    content = [p.get_text(" ", strip=True) for p in paragraphs]
    if not content or any(not p for p in content):
        raise ValueError(f"Empty paragraph in source manuscript: {slug}")
    script = "\n\n".join(content) + "\n"
    return hashlib.sha256(script.encode()).hexdigest(), len(script.split())


def audio_hash(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(file: Path) -> dict:
    """Read stream metadata via FFprobe; fail for unsupported media."""
    if not shutil.which("ffprobe"):
        raise ValueError("ffprobe unavailable: MP3 publication blocked")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,bit_rate:stream=codec_type,codec_name,channels,sample_rate,bit_rate",
         "-of", "json", str(file)], capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise ValueError(f"Unrecognized audio file {file.name}: {result.stderr[-200:]}")
    return json.loads(result.stdout)


def decode(file: Path) -> None:
    """Decode every MP3 frame, including the end of a lengthy narration."""
    if not shutil.which("ffmpeg"):
        raise ValueError("ffmpeg unavailable: MP3 publication blocked")
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-i", str(file), "-map", "0:a:0", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode:
        raise ValueError(f"MP3 decoding failed for {file.name}: {result.stderr[-200:]}")


def validate(root: Path, *, inspect=probe, fully_decode=decode) -> list[dict]:
    """Reject every unreviewed, source-mismatched, or technically invalid audio file."""
    manifest = json.loads((root / "content/audio.json").read_text())
    essays = json.loads((root / "content/essays.json").read_text())
    if not isinstance(manifest, dict) or not isinstance(essays, list):
        raise ValueError("Invalid audio manifest")
    known = {item["slug"] for item in essays}
    if set(manifest) - known:
        raise ValueError("Unknown essay in audio manifest")
    accepted = []
    for slug, metadata in manifest.items():
        if not isinstance(metadata, dict) or metadata.get("path") != f"media/{slug}.mp3":
            raise ValueError(f"Unsafe audio path: {slug}")
        file = root / metadata["path"]
        if not file.is_file() or not file.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Audio file missing or unsafe: {slug}")
        if not 50_000 <= file.stat().st_size <= 200_000_000:
            raise ValueError(f"Suspicious MP3 size: {slug}")
        sha = metadata.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha) or audio_hash(file) != sha:
            raise ValueError(f"MP3 checksum mismatch: {slug}")
        source_hash, words = manuscript_digest(root, slug)
        if metadata.get("manuscript_sha256") != source_hash:
            raise ValueError(f"Narration manuscript checksum mismatch: {slug}")
        voice = metadata.get("voice")
        if (not isinstance(voice, dict) or voice.get("type") not in ("human", "synthetic")
                or any(not isinstance(voice.get(k), str) or not voice[k].strip()
                       for k in ("name", "provider", "distribution_rights_basis"))):
            raise ValueError(f"Voice identity or distribution rights missing: {slug}")
        review = metadata.get("review")
        if (not isinstance(review, dict) or any(review.get(flag) is not True for flag in REVIEW_FLAGS)
                or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()):
            raise ValueError(f"Missing accountable full-listening review: {slug}")
        try:
            signed = date.fromisoformat(review["reviewed_on"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid review date: {slug}") from exc
        if signed > date.today():
            raise ValueError(f"Future listening-review date: {slug}")

        info = inspect(file)
        streams = info.get("streams", [])
        if (len(streams) != 1 or streams[0].get("codec_type") != "audio"
                or streams[0].get("codec_name") != "mp3"):
            raise ValueError(f"Expected one MP3 audio stream: {slug}")
        stream = streams[0]
        if int(stream.get("channels") or 0) not in (1, 2):
            raise ValueError(f"Invalid channel count: {slug}")
        if not 22050 <= int(stream.get("sample_rate") or 0) <= 96000:
            raise ValueError(f"Invalid sample rate: {slug}")
        bit_rate = int(stream.get("bit_rate") or info.get("format", {}).get("bit_rate") or 0)
        if not 48000 <= bit_rate <= 320000:
            raise ValueError(f"Invalid audio bitrate: {slug}")
        duration = float(info.get("format", {}).get("duration") or 0)
        if duration <= 0 or not 70 <= 60 * words / duration <= 260:
            raise ValueError(f"Implausible narration length: {slug}")
        fully_decode(file)
        accepted.append({"slug": slug, "duration_seconds": round(duration, 1)})
    return accepted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    results = validate(args.root)
    print(f"Verified {len(results)} reviewed MP3 files; spoken fidelity remains a human review responsibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
