#!/usr/bin/env python3
"""Prepare a private, source-verified, blinded listening page from voice auditions.

This utility never publishes audio. It refuses modified or differently worded
clips, checks each MP3's independent signal quality, and stores the identity
key separately from the anonymous offline HTML player.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import secrets
import shutil
from pathlib import Path

VOICES = ("af_heart", "bf_emma", "am_michael", "bm_george")
CLIP_NAME = "UNREVIEWED-forward-science-preview.mp3"
METADATA_NAME = "CANDIDATE-NOT-FOR-PUBLICATION.json"


def checksum(path: Path) -> str:
    """Return SHA-256 without loading an entire recording into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_candidate(path: Path, voice: str, measurement) -> dict:
    """Fail closed if a clip is untrusted, differently worded or badly mastered."""
    meta = json.loads((path / METADATA_NAME).read_text(encoding="utf-8"))
    audio = path / CLIP_NAME
    if meta["voice"] != voice or meta["essay"] != "forward-science":
        raise ValueError(f"{voice}: wrong voice or essay")
    if meta.get("publication_approved") is not False:
        raise ValueError(f"{voice}: the audition must be explicitly unreviewed")
    if checksum(audio) != meta["mp3_sha256"]:
        raise ValueError(f"{voice}: audio checksum differs from source receipt")
    sample = meta["sample_text"]
    if hashlib.sha256(sample.encode("utf-8")).hexdigest() != meta["sample_text_sha256"]:
        raise ValueError(f"{voice}: original sample text differs from receipt")
    quality = measurement(audio)
    if not -20 <= quality["integrated_lufs"] <= -16 or quality["true_peak_dbtp"] > -1:
        raise ValueError(f"{voice}: audition volume differs from the -18 LUFS target")
    return meta


def listening_html(sample: str) -> str:
    """Create an offline, zero-network comparison page without voice identities."""
    cards = []
    for letter in "ABCD":
        options = '<option value="">Score 1–5</option>' + "".join(
            f'<option value="{value}">{value}</option>' for value in range(1, 6))
        cards.append(
            f'<section class="voice"><h2>Voice {letter}</h2>'
            f'<audio controls preload="metadata" src="Voice_{letter}.mp3" '
            f'aria-label="Voice {letter} audition"></audio>'
            f'<div class="ratings">'
            f'<label>Naturalness<select id="n-{letter}">{options}</select></label>'
            f'<label>Scientific pronunciation<select id="s-{letter}">{options}</select></label>'
            f'<label>Cadence<select id="c-{letter}">{options}</select></label>'
            f'</div><label>Notes<textarea id="t-{letter}" rows="2" '
            f'placeholder="Rhythm, acronyms, breath pauses, listener fatigue..."></textarea>'
            f'</label></section>'
        )
    safe_text = html.escape(sample)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forward Science — private narrator auditions</title>
<style>
:root {{ font-family: system-ui,sans-serif; color:#263129; background:#f8f7f3; }}
* {{box-sizing:border-box}} body {{margin:0;padding:32px 18px 70px}}
main {{max-width:780px;margin:auto}} small {{letter-spacing:.08em}}
h1,h2 {{font-family:Georgia,serif;font-weight:500}}
h1 {{font-size:clamp(1.8rem,5vw,2.8rem);line-height:1.2}}
p {{color:#4b584f;line-height:1.65}} .voice {{border-top:1px solid #d2d5cf;padding:22px 0}}
audio {{width:100%;margin:10px 0 18px}} .ratings {{display:flex;gap:14px;flex-wrap:wrap}}
label {{display:flex;flex-direction:column;gap:6px;font-size:.9rem;margin-bottom:14px}}
select,textarea {{font:inherit;background:#fff;color:#263129;border:1px solid #aeb6ac;padding:7px}}
textarea {{width:100%}} details {{padding:18px 0}} summary {{cursor:pointer}}
blockquote {{line-height:1.65;font-family:Georgia,serif;white-space:pre-wrap}}
button {{padding:12px 16px;background:#263e30;color:white;border:0;cursor:pointer}}
button:focus-visible,a:focus-visible,select:focus-visible,textarea:focus-visible
{{outline:3px solid #cc8c39;outline-offset:3px}}
</style></head><body><main>
<small>FORWARD SCIENCE · PRIVATE EDITORIAL AUDITION</small>
<h1>Choose the voice by listening.</h1>
<p>Four identical source passages, independently mastered to approximately −18 LUFS.
Use headphones at 1× speed. Score first, reveal identities later.</p>
<p><strong>Unreviewed samples only.</strong> This page works offline, sends no
recordings or ratings over the network, and never starts audio automatically.</p>
<details><summary>Read the source passage to inspect pronunciation</summary>
<blockquote>{safe_text}</blockquote></details>
{''.join(cards)}
<button id="save" type="button">Save my listening review (JSON)</button>
<p id="status" role="status" aria-live="polite"></p>
<p>Open VOICE-KEY-OPEN-AFTER-LISTENING.json only once the ratings are complete.
A short audition selects candidates; it does not certify a complete recording.</p>
</main><script>
"use strict";
const clips = [...document.querySelectorAll("audio")];
clips.forEach(a => a.addEventListener("play", () => {{
  clips.forEach(b => {{ if (b !== a) b.pause(); }});
}}));
document.getElementById("save").addEventListener("click", () => {{
  const scores = {{}};
  for (const key of "ABCD") {{
    scores[key] = {{
      naturalness: document.getElementById("n-"+key).value || null,
      scientific_pronunciation: document.getElementById("s-"+key).value || null,
      cadence: document.getElementById("c-"+key).value || null,
      notes: document.getElementById("t-"+key).value.trim()
    }};
  }}
  const review = JSON.stringify({{
    project:"Forward Science", status:"UNREVIEWED_LISTENING_SCORES",
    publication_approved:false, scores
  }}, null, 2);
  const url = URL.createObjectURL(new Blob([review], {{type:"application/json"}}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "FORWARD-SCIENCE-VOICE-REVIEW.json";
  link.click();
  document.getElementById("status").textContent = "Review saved to Downloads.";
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}});
</script></body></html>
"""


def build(input_root: Path, output: Path, measurement=None) -> dict:
    """Validate a fixed four-voice corpus and write anonymized offline media."""
    if measurement is None:
        from generate_all_audio_candidates import measure_audio
        measurement = measure_audio
    input_root = input_root.resolve()
    output = output.resolve()
    repo = Path(__file__).resolve().parents[1]
    if (output == input_root or any(output.is_relative_to(input_root / v) for v in VOICES)
            or output.is_relative_to(repo / "site")
            or output.is_relative_to(repo / "content")
            or output.is_relative_to(repo / "media")):
        raise ValueError("Private audition output overlaps source or publication assets")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Private audition output must be a new empty directory")
    verified = {v: verify_candidate(input_root / v, v, measurement) for v in VOICES}
    if len({m["sample_text_sha256"] for m in verified.values()}) != 1:
        raise ValueError("Candidate voices speak different text")
    if len({m["source_narration_sha256"] for m in verified.values()}) != 1:
        raise ValueError("Candidate voices use different source manuscripts")
    order = list(VOICES)
    secrets.SystemRandom().shuffle(order)
    output.mkdir(parents=True, exist_ok=True)
    receipt = []
    for letter, voice in zip("ABCD", order, strict=True):
        source = input_root / voice / CLIP_NAME
        destination = output / f"Voice_{letter}.mp3"
        shutil.copyfile(source, destination)
        if checksum(destination) != verified[voice]["mp3_sha256"]:
            raise ValueError("Audition output changed during copy")
        receipt.append({"letter":letter, "voice":voice, "mp3_sha256":checksum(destination)})
    (output / "LISTEN-OFFLINE.html").write_text(
        listening_html(verified[order[0]]["sample_text"]), encoding="utf-8")
    (output / "VOICE-KEY-OPEN-AFTER-LISTENING.json").write_text(
        json.dumps({"mapping":receipt}, indent=2) + "\n", encoding="utf-8")
    public = {
        "status":"UNREVIEWED_AUDITIONS",
        "publication_approved":False,
        "source_narration_sha256":verified[order[0]]["source_narration_sha256"],
        "sample_text_sha256":verified[order[0]]["sample_text_sha256"],
        "source_paragraphs":2,
        "target_lufs":-18,
        "audio_sha256":{item["letter"]:item["mp3_sha256"] for item in receipt},
    }
    (output / "PROVENANCE.json").write_text(
        json.dumps(public, indent=2) + "\n", encoding="utf-8")
    (output / "READ-ME-FIRST.txt").write_text(
        "Private voice auditions. Extract the entire archive and open "
        "LISTEN-OFFLINE.html. Score the four letters on headphones before "
        "opening VOICE-KEY-OPEN-AFTER-LISTENING.json. All clips are "
        "unreviewed, unchanged original text, and not approved for publication.\n",
        encoding="utf-8",
    )
    return public


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.input, args.output)
    print("Four blind, independently mastered candidates prepared:",
          result["sample_text_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
