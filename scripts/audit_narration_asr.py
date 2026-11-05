#!/usr/bin/env python3
"""Independent ASR inspection of unreviewed Forward Science audio.

ASR never receives reference wording as a prompt. Its imperfect transcript
provides review cues and NEVER constitutes publication approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

CRITICAL = frozenset({
    "no", "not", "never", "none", "without", "only", "must", "cannot",
    "always", "every", "all", "any", "zero", "one", "two", "three",
    "first", "second", "more", "less", "before", "after", "except",
})


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^\w']+", " ", text).split()


def word_edit_distance(a: list[str], b: list[str]) -> int:
    """Exact Levenshtein word distance in linear space."""
    if len(b) > len(a):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        curr = [i]
        for j, right in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1,
                            prev[j - 1] + (left != right)))
        prev = curr
    return prev[-1]


def compare(reference: str, heard: str) -> dict:
    """Separate transcript orthography from candidate changes in spoken content.

    A spelling/spacing difference such as 'first hand' vs 'firsthand' has a
    nonzero raw WER, yet is not evidence that speech diverged. Preserve raw WER
    for reproducibility; prioritize content changes, critical qualifications
    and clearly missing audio. ASR remains fallible.
    """
    expected, recognized = tokens(reference), tokens(heard)
    if not expected:
        raise ValueError("Empty source phrase")
    wer = word_edit_distance(expected, recognized) / len(expected)
    changes, content_changes, orthography, critical = [], [], [], []
    estimated_content_edits = 0
    for kind, start, end, h_start, h_end in SequenceMatcher(
            None, expected, recognized, autojunk=False).get_opcodes():
        if kind == "equal":
            continue
        old, new = expected[start:end], recognized[h_start:h_end]
        item = {"operation": kind, "reference": " ".join(old),
                "recognized": " ".join(new)}
        changes.append(item)
        # A deterministic joining/splitting test. This is deliberately
        # conservative: it does not classify homophones as equivalent.
        if old and new and "".join(old) == "".join(new):
            orthography.append(item)
            continue
        content_changes.append(item)
        estimated_content_edits += max(len(old), len(new))
        if CRITICAL.intersection(old) or CRITICAL.intersection(new):
            critical.append(item)
    ratio = len(recognized) / len(expected)
    content_ratio = estimated_content_edits / len(expected)
    priority = ("high" if content_ratio >= .20 or ratio < .70 or critical else
                "medium" if content_ratio >= .08 else "low")
    return {
        "word_error_rate": round(wer, 5), "priority": priority,
        "reference_words": len(expected), "asr_words": len(recognized),
        "word_count_ratio": round(ratio, 3),
        "content_edit_ratio": round(content_ratio, 5),
        "critical_mismatches": critical[:12],
        "mismatch_count": len(changes), "mismatches": changes[:30],
        "orthographic_variants": orthography[:30],
        "content_mismatches": content_changes[:30],
        "human_check_needed": bool(content_changes),
    }


def validate_drafts(root: Path, drafts: Path) -> list[tuple[dict, list[tuple[str, bool]]]]:
    """Verify the six draft files, original manuscripts, and source-hashed cues."""
    from prepare_narration import compile_narration
    from generate_all_audio_candidates import segments_for

    data = json.loads((drafts / "UNREVIEWED-MANIFEST.json").read_text(encoding="utf-8"))
    if data.get("status") != "UNREVIEWED_SYNTHETIC_DRAFTS" or data.get("publication_approved") is not False:
        raise ValueError("Only explicitly unreviewed draft manifests are accepted")
    items = data.get("recordings")
    if not isinstance(items, list) or len(items) != 6:
        raise ValueError("Expected exactly six drafts")
    temporary_source = drafts / "_independent_reference"
    if temporary_source.exists():
        raise ValueError("Unexpected reference-workspace collision")
    try:
        truth = compile_narration(root, temporary_source)
        sources = {item["slug"]: item for item in truth["essays"]}
        if set(sources) != {item.get("slug") for item in items}:
            raise ValueError("Draft and source manuscript sets differ")
        verified = []
        for item in items:
            slug = item["slug"]
            if item.get("filename") != f"UNREVIEWED-{slug}.mp3":
                raise ValueError(f"Invalid candidate filename: {slug}")
            media = drafts / item["filename"]
            if not media.is_file() or media.is_symlink() or file_hash(media) != item.get("sha256"):
                raise ValueError(f"Missing or modified MP3: {slug}")
            source_digest = sources[slug]["spoken_body_sha256"]
            if item.get("manuscript_sha256") != source_digest:
                raise ValueError(f"Source manuscript digest mismatch: {slug}")
            script = drafts / "manuscripts" / f"{slug}.txt"
            if not script.is_file() or file_hash(script) != source_digest:
                raise ValueError(f"Bundled manuscript mismatch: {slug}")
            phrases = segments_for(script.read_text(encoding="utf-8"), max_chars=850)
            cues = item.get("segment_timeline")
            if not isinstance(cues, list) or len(cues) != len(phrases):
                raise ValueError(f"Invalid segment count: {slug}")
            last_end = 0.0
            for index, (cue, (phrase, _)) in enumerate(zip(cues, phrases, strict=True), 1):
                if (cue["segment"] != index or
                    cue.get("source_sha256") != hashlib.sha256(phrase.encode()).hexdigest() or
                    cue["start_seconds"] + .015 < last_end or
                    cue["start_seconds"] < 0 or
                    cue["end_seconds"] <= cue["start_seconds"]):
                    raise ValueError(f"Corrupt source phrase cue: {slug} / {index}")
                last_end = cue["end_seconds"]
            verified.append((item, phrases))
        return verified
    finally:
        shutil.rmtree(temporary_source, ignore_errors=True)


def audit(source_root: Path, drafts: Path, output: Path,
          *, transcribe: Callable[[Path, float, float], str] | None = None,
          model: str = "small.en") -> dict:
    """Compare every recorded source phrase with independent recognized speech."""
    verified = validate_drafts(source_root, drafts)
    output.mkdir(parents=True, exist_ok=True)
    if transcribe is None:
        from faster_whisper import WhisperModel
        from faster_whisper.audio import decode_audio

        recognizer = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=4)

        def transcribe_file(path: Path, cues: list[dict]) -> list[str]:
            audio = decode_audio(str(path), sampling_rate=16000)
            if cues[-1]["end_seconds"] > len(audio) / 16000 + .20:
                raise ValueError(f"Source timeline exceeds recording: {path.name}")
            results = []
            for cue in cues:
                start = max(0, int((cue["start_seconds"] - .08) * 16000))
                end = min(len(audio), int((cue["end_seconds"] + .08) * 16000))
                if end <= start:
                    raise ValueError(f"Empty speech window in {path.name}")
                segments, _ = recognizer.transcribe(
                    audio[start:end], language="en", beam_size=5, temperature=0,
                    vad_filter=False, condition_on_previous_text=False,
                )
                results.append(" ".join(s.text.strip() for s in segments).strip())
            return results
    else:
        def transcribe_file(path: Path, cues: list[dict]) -> list[str]:
            return [transcribe(path, c["start_seconds"], c["end_seconds"]) for c in cues]

    chapters, review = [], []
    for item, phrases in verified:
        slug = item["slug"]
        cues = item["segment_timeline"]
        transcriptions = transcribe_file(drafts / item["filename"], cues)
        if len(transcriptions) != len(phrases):
            raise ValueError(f"Incomplete transcription: {slug}")
        results = []
        for cue, (reference, _), heard in zip(cues, phrases, transcriptions, strict=True):
            verdict = compare(reference, heard)
            row = {
                "slug": slug, "segment": cue["segment"], "paragraph": cue["paragraph"],
                "start_seconds": cue["start_seconds"], "end_seconds": cue["end_seconds"],
                "reference": reference, "recognized": heard, **verdict,
            }
            results.append(row)
            if row["human_check_needed"] or row["priority"] != "low":
                review.append(row)
        priorities = dict(Counter(x["priority"] for x in results))
        chapters.append({"slug": slug, "segments": results, "priorities": priorities})
        print(f"ASR AUDIT {slug}: {len(results)} phrases; {priorities}", flush=True)

    summary = {
        "chapters": len(chapters), "segments": sum(len(c["segments"]) for c in chapters),
        "high_priority": sum(c["priorities"].get("high", 0) for c in chapters),
        "medium_priority": sum(c["priorities"].get("medium", 0) for c in chapters),
        "source_fidelity_review_segments": len(review),
        "orthographic_only_segments": sum(
            bool(s["orthographic_variants"]) and not s["human_check_needed"]
            for c in chapters for s in c["segments"]
        ),
    }
    report = {
        "status": "UNREVIEWED_AUTOMATED_INSPECTION_ONLY",
        "source_manifest_sha256": file_hash(drafts / "UNREVIEWED-MANIFEST.json"),
        "asr_model": model,
        "asr_model_revision": os.environ.get("ASR_MODEL_REVISION", "unspecified"),
        "summary": summary,
        "chapters": chapters,
        "publication_approved": False,
        "limitations": "ASR is imperfect; results are listening-review cues, not spoken-text certification.",
    }
    (output / "ASR_AUDIT_UNREVIEWED.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Forward Science — Independent narration listening queue", "",
        "**UNREVIEWED. NO PUBLICATION APPROVAL.**",
        "ASR receives only audio. Even low estimated WER does not establish that spoken text is complete.",
        "Listen to all six recordings against their original manuscripts.", "",
        f"Total phrases: {summary['segments']}. High-priority: {summary['high_priority']}. "
        f"Medium-priority: {summary['medium_priority']}. "
        f"All meaningful ASR discrepancies: {summary['source_fidelity_review_segments']}.", "",
        "Spelling-only changes are retained in JSON but do not raise review priority.",
        "Phrases flagged here are listening targets, not confirmed audio errors.", "",
    ]
    for row in sorted(review, key=lambda x: (
        x["priority"] != "high", -x["word_error_rate"], x["slug"], x["segment"]
    )):
        lines.extend([
            f"## {row['slug']} / phrase {row['segment']} / "
            f"{row['start_seconds']:.1f}–{row['end_seconds']:.1f}s",
            f"Priority: {row['priority']} — approximate raw WER {row['word_error_rate']:.1%}; "
            f"content-edit estimate {row['content_edit_ratio']:.1%}",
            f"**Reference:** {row['reference']}",
            f"**ASR heard:** {row['recognized'] or '(no recognized words)'}",
            "Candidate content differences: " + json.dumps(
                row["content_mismatches"], ensure_ascii=False),
            "Critical mismatches: " + json.dumps(row["critical_mismatches"], ensure_ascii=False)
            if row["critical_mismatches"] else "", "",
        ])
    (output / "HUMAN_LISTENING_QUEUE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--drafts", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("asr-review"))
    parser.add_argument("--model", default="small.en")
    args = parser.parse_args()
    audit(args.source_root, args.drafts, args.output, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
