#!/usr/bin/env python3
"""Verify six source-matched, explicitly unreviewed audio previews.

These previews have author permission to be publicly auditioned. This module
never produces or impersonates the final signed recording-approval manifest.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    """Stream a file's SHA-256 to avoid loading long recordings into memory."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def media_check(file: Path, words: int) -> None:
    """Verify a real, fully decodable MP3 with a plausible spoken duration."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,channels,sample_rate",
         "-of", "json", str(file)],
        capture_output=True, text=True, timeout=40,
    )
    if result.returncode:
        raise ValueError(f"Unable to inspect preview MP3: {file.name}")
    try:
        report = json.loads(result.stdout)
        streams = report["streams"]
        stream = streams[0]
        duration = float(report["format"]["duration"])
        valid = (
            len(streams) == 1 and stream["codec_type"] == "audio"
            and stream["codec_name"] == "mp3"
            and int(stream["channels"]) in (1, 2)
            and 22050 <= int(stream["sample_rate"]) <= 96000
            and 70 <= (60 * words / duration) <= 260
        )
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid preview MP3 metadata: {file.name}") from exc
    if not valid:
        raise ValueError(f"Unexpected MP3 format or narration duration: {file.name}")
    decoded = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-xerror",
         "-i", str(file), "-map", "0:a:0", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    if decoded.returncode:
        raise ValueError(f"Preview MP3 fails complete decoding: {file.name}")


def source_digest(root: Path, slug: str) -> tuple[str, int]:
    """Reuse the final-release manuscript compiler to establish text identity."""
    path = Path(__file__).with_name("verify_audio.py")
    spec = importlib.util.spec_from_file_location("forward_science_preview_source", path)
    if spec is None or spec.loader is None:
        raise ValueError("Missing original manuscript verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.manuscript_digest(root, slug)


def validate(root: Path, folder: Path, *, inspect=media_check) -> dict[str, dict]:
    """Return checked media paths, rejecting any modified or unapproved source."""
    root = root.resolve()
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Missing or unsafe private preview artifact")
    folder = folder.resolve()
    pinned = json.loads((root / "content/audio-previews.json").read_text(encoding="utf-8"))
    original = json.loads((root / "content/essays.json").read_text(encoding="utf-8"))
    expected = {entry["slug"] for entry in original}
    if (set(pinned["recordings"]) != expected
            or pinned.get("status") != "PUBLIC_PREVIEW_UNREVIEWED"
            or pinned.get("publication_approved") is not False
            or pinned.get("artifact_run_id") != 42388856204
            or pinned.get("voice") != "am_michael"
            or pinned.get("tts_speed") != 1.10):
        raise ValueError("Public-preview authorization metadata is inconsistent")
    receipt = folder / "UNREVIEWED-MANIFEST.json"
    if not receipt.is_file() or receipt.is_symlink():
        raise ValueError("Missing private production receipt")
    if digest(receipt) != pinned.get("source_manifest_sha256"):
        raise ValueError("Private production receipt hash differs from pinned manifest")
    report = json.loads(receipt.read_text(encoding="utf-8"))
    if (report.get("status") != "UNREVIEWED_SYNTHETIC_DRAFTS"
            or report.get("publication_approved") is not False
            or report.get("voice") != pinned["voice"]
            or report.get("tts_speed") != pinned["tts_speed"]):
        raise ValueError("Source recording identity or preview review state changed")
    recordings = report.get("recordings")
    if not isinstance(recordings, list) or len(recordings) != 6:
        raise ValueError("Expected exactly six full-length preview recordings")
    if {r.get("slug") for r in recordings} != expected:
        raise ValueError("Preview recordings do not cover the six essays")
    media_names = {f"UNREVIEWED-{slug}.mp3" for slug in expected}
    if {path.name for path in folder.glob("*.mp3")} != media_names:
        raise ValueError("Unexpected or missing MP3 in preview artifact")
    accepted = {}
    for row in recordings:
        slug = row["slug"]
        pin = pinned["recordings"][slug]
        filename = f"UNREVIEWED-{slug}.mp3"
        media = folder / filename
        manuscript = folder / "manuscripts" / f"{slug}.txt"
        if (row.get("filename") != filename
                or not media.is_file() or media.is_symlink()
                or not manuscript.is_file() or manuscript.is_symlink()
                or not media.resolve().is_relative_to(folder)
                or not manuscript.resolve().is_relative_to(folder)
                or media.stat().st_size < 50_000
                or media.stat().st_size > 100_000_000):
            raise ValueError(f"Missing or unsafe preview file: {slug}")
        source_sha, words = source_digest(root, slug)
        if (row.get("approved_for_publication") is not False
                or row.get("reviewed") is not False
                or row.get("tts_speed") != 1.10
                or not re.fullmatch(r"[0-9a-f]{64}", pin.get("sha256", ""))
                or row.get("sha256") != pin["sha256"]
                or digest(media) != pin["sha256"]
                or row.get("manuscript_sha256") != source_sha
                or pin.get("manuscript_sha256") != source_sha
                or digest(manuscript) != source_sha):
            raise ValueError(f"Unreviewed preview or source manuscript changed: {slug}")
        quality = row.get("signal_quality", {})
        if (not -21 <= quality.get("integrated_lufs", float("-inf")) <= -15
                or quality.get("true_peak_dbtp", float("inf")) > -1
                or quality.get("silences_over_2_5_seconds") != 0):
            raise ValueError(f"Preview signal-quality measurements unacceptable: {slug}")
        inspect(media, words)
        accepted[slug] = {
            "file": media,
            "sha256": pin["sha256"],
            "path": f"media/preview-{slug}.mp3",
            "voice": {"type": "synthetic", "name": "Michael", "provider": "Kokoro-82M"},
            "preview": True,
        }
    return accepted
