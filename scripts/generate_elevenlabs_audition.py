#!/usr/bin/env python3
"""Prepare or explicitly purchase one *unreviewed* ElevenLabs narrator audition.

Default invocation is a network-free cost/identity preview. A paid API request
occurs only with --execute, a selected --voice-id, sufficient --max-credits,
and ELEVENLABS_API_KEY. Outputs are private review artifacts, never a public
audio release. No API key is written to disk or included in error messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MODEL = "eleven_multilingual_v2"
VOICE_ID = re.compile(r"^[A-Za-z0-9_-]{15,100}$")
AUDIO_LIMIT = 8_000_000
SAMPLE_LIMIT = 4_000
OUTPUT_NAME = "UNREVIEWED-elevenlabs-forward-science-preview.mp3"


def verified_sample(root: Path = ROOT) -> tuple[str, str]:
    """Use exactly the same opening two paragraphs as the Kokoro audition."""
    import sys
    script_dir = str(root / "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from prepare_narration import compile_narration

    with tempfile.TemporaryDirectory(prefix="fs-narration-") as tmp:
        folder = Path(tmp)
        metadata = compile_narration(root, folder)
        source = next(e for e in metadata["essays"] if e["slug"] == "forward-science")
        manuscript = (folder / "forward-science.txt").read_text(encoding="utf-8")
        paragraphs = manuscript.split("\n\n")
        if len(paragraphs) < 3:
            raise ValueError("Expected at least two substantive source paragraphs")
        sample = " ".join(paragraphs[:2]).strip()
        if not sample or len(sample) > SAMPLE_LIMIT:
            raise ValueError("Unreasonable audition text length")
        return sample, source["spoken_body_sha256"]


def safe_output(root: Path, target: Path) -> Path:
    """Keep unreviewed voice files away from all published and authoritative data."""
    destination = target.resolve()
    project = root.resolve()
    if (destination == project or destination == project / "site"
            or destination.is_relative_to(project / "site")
            or destination.is_relative_to(project / "content")
            or destination.is_relative_to(project / "media")
            or destination.is_relative_to(project / ".github")
            or destination.is_relative_to(project / "docs")
            or destination.is_relative_to(project / "templates")
            or destination.is_relative_to(project / "scripts")
            or destination.is_relative_to(project / "tests")):
        raise ValueError("Unreviewed audio output must not overlap project authority or site")
    if target.is_symlink():
        raise ValueError("Refusing symlinked output directory")
    return destination


def request_audio(voice_id: str, text: str, key: str) -> bytes:
    """Execute one billable HTTP request, with strict host, format and size."""
    url = ("https://api.elevenlabs.io/v1/text-to-speech/"
           + quote(voice_id, safe="") + "?output_format=mp3_44100_128")
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": 0.6, "similarity_boost": 0.75,
            "style": 0.0, "use_speaker_boost": True,
        },
    }).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
        "User-Agent": "ForwardScience-NarrationAudition/1.0",
    })
    try:
        with urlopen(req, timeout=150) as response:
            if response.status != 200:
                raise RuntimeError(f"ElevenLabs returned HTTP {response.status}")
            if response.headers.get_content_type() not in ("audio/mpeg", "audio/mp3"):
                raise RuntimeError("ElevenLabs did not return an MP3 audio response")
            payload = response.read(AUDIO_LIMIT + 1)
    except HTTPError as exc:
        raise RuntimeError(f"ElevenLabs rejected audition request (HTTP {exc.code})") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("ElevenLabs audition network request failed; inspect credit history before retrying") from None
    if not 32_000 <= len(payload) <= AUDIO_LIMIT:
        raise RuntimeError("Unexpected audio byte length; request discarded")
    return payload


def verify_mp3(path: Path) -> float:
    """Reject a non-MP3 or truncated/implausibly short audio response."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_name,codec_type:format=duration",
            "-of", "json", str(path),
        ], capture_output=True, text=True, timeout=30, check=True)
        parsed = json.loads(result.stdout)
        streams = [x for x in parsed["streams"] if x.get("codec_type") == "audio"]
        duration = float(parsed["format"]["duration"])
    except (subprocess.CalledProcessError, FileNotFoundError, KeyError,
            TypeError, ValueError, OSError, TimeoutError) as exc:
        raise ValueError("Unreviewed ElevenLabs MP3 failed media validation") from exc
    if len(streams) != 1 or streams[0].get("codec_name") != "mp3" or not 15 <= duration <= 900:
        raise ValueError("Invalid codec, stream count, or audition duration")
    return duration


def audition(
    root: Path, output: Path, voice_id: str | None, execute: bool,
    max_credits: int = 0,
    transport: Callable[[str, str, str], bytes] = request_audio,
    validator: Callable[[Path], float] = verify_mp3,
) -> dict:
    """Produce a read-only plan or a single, unreviewed billable sample."""
    sample, manuscript_sha = verified_sample(root)
    estimated_credits = len(sample)
    destination = safe_output(root, output)
    if voice_id is not None and not VOICE_ID.fullmatch(voice_id):
        raise ValueError("Voice ID must be an explicitly selected valid ElevenLabs ID")
    if execute:
        if not voice_id:
            raise ValueError("--execute requires an explicitly selected voice ID")
        if max_credits <= 0 or estimated_credits > max_credits:
            raise ValueError("Estimated charge exceeds --max-credits (one credit per character)")
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key or len(key) < 10:
            raise ValueError("Missing ELEVENLABS_API_KEY environment variable")
        if (destination / OUTPUT_NAME).exists():
            raise ValueError("Unreviewed MP3 already exists; refusing a duplicate paid generation")
    report = {
        "status": "UNREVIEWED_AUDIO" if execute else "NO_CHARGE_PREVIEW",
        "publication_approved": False,
        "provider": "ElevenLabs",
        "model": MODEL,
        "voice_id": voice_id,
        "sample_text_sha256": hashlib.sha256(sample.encode("utf-8")).hexdigest(),
        "manuscript_sha256": manuscript_sha,
        "source_paragraphs": 2,
        "sample_characters": len(sample),
        "estimated_credits": estimated_credits,
        "note": "One-credit-per-character estimate; actual account billing controls apply.",
    }
    if execute:
        # A response timeout leaves charge status uncertain. Never retry automatically.
        audio = transport(voice_id, sample, key)
        if not isinstance(audio, bytes) or not 32_000 <= len(audio) <= AUDIO_LIMIT:
            raise ValueError("TTS response was not a bounded MP3 byte stream")
        destination.mkdir(parents=True, exist_ok=True)
        temp = destination / (OUTPUT_NAME + ".tmp")
        try:
            temp.write_bytes(audio)
            duration = validator(temp)
            temp.replace(destination / OUTPUT_NAME)
        finally:
            temp.unlink(missing_ok=True)
        report.update(filename=OUTPUT_NAME, mp3_sha256=hashlib.sha256(audio).hexdigest(),
                      duration_seconds=duration, full_listening_review=False,
                      distribution_rights_confirmed=False)
    else:
        destination.mkdir(parents=True, exist_ok=True)
    (destination / "AUDITION-UNREVIEWED.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice-id", help="Explicitly chosen voice from the user's ElevenLabs account")
    parser.add_argument("--max-credits", type=int, default=0,
                        help="Hard gate on estimated one-credit-per-character charge")
    parser.add_argument("--execute", action="store_true",
                        help="Authorize exactly one billable synthesis request")
    args = parser.parse_args()
    try:
        report = audition(args.root, args.output, args.voice_id, args.execute, args.max_credits)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Audition stopped: {exc}\n")
    print(("UNREVIEWED audio created" if args.execute else "NO CHARGE: preview only")
          + f" — {report['sample_characters']} characters, "
          + f"estimated {report['estimated_credits']} credits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
