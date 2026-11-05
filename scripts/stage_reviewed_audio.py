#!/usr/bin/env python3
"""Stage reviewed synthetic MP3s from private notes; never publish automatically."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

FLAGS = ("listened_in_full", "spoken_text_checked", "pronunciation_checked",
         "audio_artifacts_checked", "distribution_rights_confirmed")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object in {path}")
    return data


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def verify_release(root: Path) -> None:
    """Use exactly the same media-acceptance gate as the production build."""
    import importlib.util
    path = Path(__file__).with_name("verify_audio.py")
    spec = importlib.util.spec_from_file_location("stage_verified_audio", path)
    if spec is None or spec.loader is None:
        raise ValueError("Production audio verifier is unavailable")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    if len(verifier.validate(root)) != 6:
        raise ValueError("Six approved recordings did not pass the media gate")


def stage(source: Path, drafts: Path, asr: Path, notes: Path, approval: Path,
          output: Path, *, validator=verify_release) -> Path:
    """Verify evidence, then atomically prepare a private, unpublished release bundle."""
    source, drafts, output = source.resolve(), drafts.resolve(), output.resolve()
    if output.exists() or output in (source, drafts):
        raise ValueError("Output must be a new, separate private directory")
    expected = {e["slug"] for e in json.loads(
        (source / "content/essays.json").read_text(encoding="utf-8")
    )}
    manifest_file = drafts / "UNREVIEWED-MANIFEST.json"
    source_manifest = read_json(manifest_file)
    if (source_manifest.get("status") != "UNREVIEWED_SYNTHETIC_DRAFTS"
            or source_manifest.get("publication_approved") is not False):
        raise ValueError("Source must be an unreviewed draft archive")
    records = source_manifest.get("recordings")
    if not isinstance(records, list) or len(records) != 6 or {r["slug"] for r in records} != expected:
        raise ValueError("Candidate archive does not contain exactly six essays")
    audit = read_json(asr)
    if (audit.get("source_manifest_sha256") != digest(manifest_file)
            or audit.get("publication_approved") is not False
            or {c["slug"] for c in audit.get("chapters", [])} != expected):
        raise ValueError("Independent ASR evidence is incomplete or mismatched")
    review = read_json(notes)
    if (review.get("kind") != "UNREVIEWED_NARRATION_WORKING_NOTES"
            or review.get("publication_approved") is not False
            or {c["slug"] for c in review.get("recordings", [])} != expected):
        raise ValueError("Private review notes are missing or incomplete")
    per_slug = {x["slug"]: x for x in review["recordings"]}
    asr_by_slug = {x["slug"]: x for x in audit["chapters"]}
    signed = read_json(approval)
    if signed.get("authorize_release_candidate") is not True:
        raise ValueError("Missing affirmative human release-candidate authorization")
    reviewer = signed.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Missing accountable reviewer")
    try:
        review_date = date.fromisoformat(signed["reviewed_on"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Review date must be ISO YYYY-MM-DD") from exc
    if review_date > date.today():
        raise ValueError("The reviewer date is in the future")
    flags = signed.get("attestations")
    if not isinstance(flags, dict) or any(flags.get(name) is not True for name in FLAGS):
        raise ValueError("Actual listening and rights attestations are incomplete")
    voice = signed.get("voice")
    if (not isinstance(voice, dict) or voice.get("type") != "synthetic"
            or voice.get("name") != source_manifest.get("voice")
            or any(not isinstance(voice.get(key), str) or not voice[key].strip()
                   for key in ("name", "provider", "distribution_rights_basis"))):
        raise ValueError("Synthetic voice identity or distribution rights unresolved")

    approved = []
    for row in records:
        slug = row["slug"]
        media = drafts / row["filename"]
        manuscript = drafts / "manuscripts" / f"{slug}.txt"
        if row["filename"] != f"UNREVIEWED-{slug}.mp3" or media.is_symlink():
            raise ValueError(f"Untrusted audio filename: {slug}")
        if (not media.is_file() or digest(media) != row["sha256"]
                or not manuscript.is_file() or digest(manuscript) != row["manuscript_sha256"]):
            raise ValueError(f"Recording/manuscript checksum changed: {slug}")
        note = per_slug[slug]
        if (note.get("sha256") != row["sha256"]
                or note.get("manuscript_sha256") != row["manuscript_sha256"]
                or note.get("segment_count") != row["chunks"]):
            raise ValueError(f"Review decisions refer to different audio: {slug}")
        decisions = note.get("notes")
        if not isinstance(decisions, dict) or decisions.get("__fullListened") is not True:
            raise ValueError(f"Full-length listening remains unconfirmed: {slug}")
        if any(isinstance(item, dict) and item.get("status") == "problem"
               for item in decisions.values()):
            raise ValueError(f"An unresolved audio problem remains: {slug}")
        segments = asr_by_slug[slug].get("segments", [])
        if (len(segments) != row["chunks"]
                or {item["segment"] for item in segments} != set(range(1, row["chunks"] + 1))):
            raise ValueError(f"ASR audit does not cover every speech segment: {slug}")
        for item in segments:
            if item.get("mismatch_count", 0):
                answer = decisions.get(str(item["segment"]))
                if (not isinstance(answer, dict) or answer.get("status") != "checked"
                        or not isinstance(answer.get("note"), str)
                        or len(answer["note"].strip()) < 8):
                    raise ValueError(f"Unresolved ASR finding: {slug} phrase {item['segment']}")
        approved.append((slug, media, row))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".forward-science-review-", dir=output.parent) as temporary:
        temp = Path(temporary)
        check = temp / "check"
        shutil.copytree(source / "content", check / "content")
        (check / "media").mkdir()
        manifest = {}
        for slug, media, row in approved:
            target = check / "media" / f"{slug}.mp3"
            shutil.copyfile(media, target)
            if digest(target) != row["sha256"]:
                raise ValueError(f"Audio changed while staging: {slug}")
            manifest[slug] = {
                "path": f"media/{slug}.mp3", "sha256": row["sha256"],
                "manuscript_sha256": row["manuscript_sha256"],
                "voice": voice,
                "review": {
                    "reviewer": reviewer.strip(), "reviewed_on": review_date.isoformat(),
                    **{key: flags[key] for key in FLAGS},
                },
            }
        (check / "content/audio.json").write_text(json.dumps(manifest, indent=2) + "\n")
        validator(check)
        bundle = temp / "bundle"
        (bundle / "media").mkdir(parents=True)
        for slug, _, _ in approved:
            shutil.copyfile(check / "media" / f"{slug}.mp3", bundle / "media" / f"{slug}.mp3")
        (bundle / "audio.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (bundle / "RELEASE-RECEIPT.json").write_text(json.dumps({
            "status": "READY_FOR_REVIEWED_GIT_PUBLICATION",
            "published": False,
            "reviewer": reviewer, "reviewed_on": review_date.isoformat(),
            "review_notes_sha256": digest(notes), "asr_report_sha256": digest(asr),
            "draft_manifest_sha256": digest(manifest_file),
            "voice": voice, "recordings": [s for s, _, _ in approved],
        }, indent=2) + "\n")
        bundle.rename(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--drafts", type=Path, required=True)
    parser.add_argument("--asr", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print("Private release bundle staged:", stage(
        args.source, args.drafts, args.asr, args.notes, args.approval, args.output
    ))


if __name__ == "__main__":
    main()
