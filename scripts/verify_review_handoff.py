#!/usr/bin/env python3
"""Check a PRIVATE six-essay review ZIP against authoritative essay source.

This is provenance/package verification, not listening review or publication.
No recording or reviewer data is uploaded or committed by this command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from generate_all_audio_candidates import segments_for
from verify_audio import manuscript_digest

MAX_UNCOMPRESSED = 300_000_000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_object(z: ZipFile, name: str) -> dict:
    try:
        value = json.loads(z.read(name))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid or absent JSON evidence: {name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {name}")
    return value


def validate_names(z: ZipFile) -> set[str]:
    names: set[str] = set()
    size = 0
    for entry in z.infolist():
        name = entry.filename
        if (not name or name.startswith("/") or "\\" in name or "//" in name
                or PurePosixPath(name).as_posix() != name
                or any(part in (".", "..") for part in name.split("/"))
                or stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK
                or name in names):
            raise ValueError(f"Unsafe or duplicated ZIP path: {name}")
        names.add(name)
        size += entry.file_size
        if size > MAX_UNCOMPRESSED:
            raise ValueError("Excessive uncompressed size in review ZIP")
    return names


def verify(path: Path, root: Path) -> dict:
    """Verify hashes, all six original scripts and all independent ASR phrases."""
    expected = {row["slug"] for row in json.loads(
        (root / "content" / "essays.json").read_text(encoding="utf-8")
    )}
    if len(expected) != 6:
        raise ValueError("Six source essays are required")
    with ZipFile(path) as z:
        names = validate_names(z)
        required = {
            "review.html", "UNREVIEWED-MANIFEST.json",
            "ASR_AUDIT_UNREVIEWED.json", "CHECKSUMS.sha256",
            "UNSIGNED-narration-approval.template.json",
        }
        required |= {f"UNREVIEWED-{slug}.mp3" for slug in expected}
        required |= {f"manuscripts/{slug}.txt" for slug in expected}
        if required - names:
            raise ValueError(f"Missing release-review evidence: {sorted(required - names)}")

        inventory: dict[str, str] = {}
        for line in z.read("CHECKSUMS.sha256").decode("utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (\S+)", line)
            if match is None or match.group(2) in inventory:
                raise ValueError("Malformed or duplicated checksum entry")
            inventory[match.group(2)] = match.group(1)
        if set(inventory) != names - {"CHECKSUMS.sha256"}:
            raise ValueError("Checksum inventory does not cover the private archive")
        for name, expected_sha in inventory.items():
            hasher = hashlib.sha256()
            with z.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            if hasher.hexdigest() != expected_sha:
                raise ValueError(f"Review ZIP checksum mismatch: {name}")

        raw = z.read("UNREVIEWED-MANIFEST.json")
        manifest = read_object(z, "UNREVIEWED-MANIFEST.json")
        audit = read_object(z, "ASR_AUDIT_UNREVIEWED.json")
        unsigned = read_object(z, "UNSIGNED-narration-approval.template.json")
        if (manifest.get("status") != "UNREVIEWED_SYNTHETIC_DRAFTS"
                or manifest.get("publication_approved") is not False
                or audit.get("publication_approved") is not False
                or audit.get("source_manifest_sha256") != digest(raw)
                or unsigned.get("authorize_release_candidate") is not False
                or set(unsigned.get("attestations", {})) != {
                    "listened_in_full", "spoken_text_checked", "pronunciation_checked",
                    "audio_artifacts_checked", "distribution_rights_confirmed"}
                or any(value is not False for value in unsigned["attestations"].values())):
            raise ValueError("Incomplete, unbound or preapproved review evidence")
        records = manifest.get("recordings")
        chapters = audit.get("chapters")
        if not isinstance(records, list) or not isinstance(chapters, list):
            raise ValueError("Missing recording or transcript collection")
        if len(records) != 6 or len(chapters) != 6:
            raise ValueError("Incomplete six-essay review set")
        rec = {x["slug"]: x for x in records}
        by_slug = {x["slug"]: x for x in chapters}
        if len(rec) != 6 or len(by_slug) != 6 or set(rec) != expected or set(by_slug) != expected:
            raise ValueError("Review evidence does not cover the six authoritative essays")

        html = z.read("review.html").decode("utf-8")
        match = re.search(r'<script id="data" type="application/json">([\s\S]*?)</script>', html)
        if match is None:
            raise ValueError("Review HTML lacks source-hash bindings")
        html_records = json.loads(match.group(1))
        html_rows = {x["slug"]: x for x in html_records}
        if len(html_records) != 6 or set(html_rows) != expected:
            raise ValueError("Review interface recording set differs from verified set")

        ui_match = re.search(
            r'<script id="asrData" type="application/json">([\s\S]*?)</script>', html
        )
        if ui_match is None:
            raise ValueError("Review interface lacks independent ASR discrepancy controls")
        ui_flags = json.loads(ui_match.group(1))
        if not isinstance(ui_flags, dict) or set(ui_flags) != expected:
            raise ValueError("Review interface omits ASR chapter discrepancy evidence")

        count = differences = 0
        for slug in sorted(expected):
            row = rec[slug]
            audio_name = f"UNREVIEWED-{slug}.mp3"
            manuscript = z.read(f"manuscripts/{slug}.txt")
            original_hash, _ = manuscript_digest(root, slug)
            if (row.get("status") != "UNREVIEWED_DRAFT"
                    or row.get("approved_for_publication") is not False
                    or row.get("filename") != audio_name
                    or row.get("sha256") != inventory[audio_name]
                    or html_rows[slug].get("sha256") != inventory[audio_name]
                    or html_rows[slug].get("file") != audio_name
                    or row.get("manuscript_sha256") != original_hash
                    or html_rows[slug].get("manuscript_sha256") != original_hash
                    or digest(manuscript) != original_hash):
                raise ValueError(f"MP3/manuscript source identity is not established: {slug}")
            phrases = segments_for(manuscript.decode("utf-8"), max_chars=850)
            cues = row.get("segment_timeline")
            found = by_slug[slug].get("segments")
            if (not isinstance(cues, list) or not isinstance(found, list)
                    or len(cues) != len(phrases) or len(found) != len(phrases)
                    or row.get("chunks") != len(phrases)):
                raise ValueError(f"ASR source coverage is incomplete: {slug}")
            expected_review_flags = []
            for difference in found:
                if not difference.get("mismatch_count", 0):
                    continue
                changes = difference.get("mismatches")
                if not isinstance(changes, list) or not changes:
                    raise ValueError(f"Missing ASR word-difference evidence: {slug}")
                orthographic = all(
                    str(item.get("reference", "")).replace(" ", "") ==
                    str(item.get("recognized", "")).replace(" ", "")
                    for item in changes
                )
                expected_review_flags.append({
                    "segment": difference["segment"],
                    "reference": difference["reference"],
                    "recognized": difference.get("recognized", ""),
                    "word_error_rate": difference.get("word_error_rate"),
                    "discrepancies": changes,
                    "difference_type": ("orthography-only" if orthographic
                                        else "potential-content"),
                    "start_seconds": difference.get("start_seconds"),
                    "end_seconds": difference.get("end_seconds"),
                })
            if ui_flags[slug] != expected_review_flags:
                raise ValueError(
                    f"Review interface omits, changes, or misclassifies ASR differences: {slug}"
                )
            for i, (cue, asr_row, (phrase, _)) in enumerate(
                    zip(cues, found, phrases, strict=True), 1):
                if (cue.get("segment") != i or asr_row.get("segment") != i
                        or cue.get("source_sha256") != digest(phrase.encode())
                        or asr_row.get("reference") != phrase
                        or cue.get("end_seconds", 0) <= cue.get("start_seconds", 0)):
                    raise ValueError(f"Source-linked speech segment mismatch: {slug} #{i}")
                differences += bool(asr_row.get("mismatch_count", 0))
                count += 1
        return {
            "status": "PACKAGING_VERIFIED__NOT_APPROVED_FOR_PUBLICATION",
            "recordings": 6, "source_linked_segments": count,
            "asr_different_segments": differences,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.source), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
