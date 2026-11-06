"""Private reviewer handoff: all audio and ASR evidence remains source-bound."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "review_archive", ROOT / "scripts" / "verify_review_handoff.py")
assert spec is not None and spec.loader is not None
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    """Construct a six-essay archive with inert fake MP3 bytes."""
    from generate_all_audio_candidates import segments_for
    from prepare_narration import compile_narration

    folder = tmp_path_factory.mktemp("review-handoff")
    prepared = compile_narration(ROOT, folder / "manuscripts")
    audio, chapters, html_entries = [], [], []
    entries: dict[str, bytes] = {}
    for essay in prepared["essays"]:
        slug = essay["slug"]
        source = (folder / "manuscripts" / f"{slug}.txt").read_bytes()
        mp3 = b"INERT_TEST_AUDIO__" + slug.encode() * 3000
        name = f"UNREVIEWED-{slug}.mp3"
        entries[name] = mp3
        entries[f"manuscripts/{slug}.txt"] = source
        phrases = segments_for(source.decode("utf-8"), max_chars=850)
        cues = [
            {"segment": i, "source_sha256": verifier.digest(text.encode()),
             "start_seconds": float(i), "end_seconds": float(i + 1)}
            for i, (text, _) in enumerate(phrases, 1)
        ]
        audio.append({
            "slug": slug, "filename": name,
            "sha256": verifier.digest(mp3),
            "manuscript_sha256": verifier.digest(source),
            "chunks": len(phrases), "segment_timeline": cues,
            "status": "UNREVIEWED_DRAFT", "approved_for_publication": False,
        })
        chapters.append({"slug": slug, "segments": [
            {
                "segment": i, "reference": text,
                "recognized": text + " ADDITIONAL" if i == 1 else text,
                "mismatch_count": int(i == 1),
                "mismatches": ([{
                    "operation": "insert", "reference": "", "recognized": "ADDITIONAL",
                }] if i == 1 else []),
                "word_error_rate": 0.1 if i == 1 else 0.0,
                "start_seconds": float(i), "end_seconds": float(i + 1),
            }
            for i, (text, _) in enumerate(phrases, 1)
        ]})
        html_entries.append({
            "slug": slug, "file": name,
            "sha256": verifier.digest(mp3),
            "manuscript_sha256": verifier.digest(source),
        })
    manifest = json.dumps({
        "status": "UNREVIEWED_SYNTHETIC_DRAFTS",
        "publication_approved": False,
        "recordings": audio,
    }).encode()
    audit = json.dumps({
        "publication_approved": False,
        "source_manifest_sha256": verifier.digest(manifest),
        "chapters": chapters,
    }).encode()
    approval = json.dumps({
        "authorize_release_candidate": False,
        "attestations": {
            "listened_in_full": False, "spoken_text_checked": False,
            "pronunciation_checked": False, "audio_artifacts_checked": False,
            "distribution_rights_confirmed": False,
        },
    }).encode()
    asr_flags = {
        chapter["slug"]: [
            {
                "segment": row["segment"], "reference": row["reference"],
                "recognized": row["recognized"],
                "word_error_rate": row["word_error_rate"],
                "discrepancies": row["mismatches"],
                "difference_type": "potential-content",
                "start_seconds": row["start_seconds"],
                "end_seconds": row["end_seconds"],
            }
            for row in chapter["segments"] if row["mismatch_count"]
        ]
        for chapter in chapters
    }
    entries.update({
        "UNREVIEWED-MANIFEST.json": manifest,
        "ASR_AUDIT_UNREVIEWED.json": audit,
        "UNSIGNED-narration-approval.template.json": approval,
        "review.html": (
            '<script id="data" type="application/json">'
            + json.dumps(html_entries) + '</script>'
            + '<script id="asrData" type="application/json">'
            + json.dumps(asr_flags) + '</script>'
        ).encode(),
    })
    return entries


def packaged(tmp_path, entries):
    archive = tmp_path / "private-review.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
        for name, contents in entries.items():
            z.writestr(name, contents)
        receipts = "".join(
            f"{verifier.digest(contents)}  {name}\n"
            for name, contents in sorted(entries.items())
        )
        z.writestr("CHECKSUMS.sha256", receipts)
    return archive


def test_private_handoff_has_six_source_linked_recordings(tmp_path, evidence):
    result = verifier.verify(packaged(tmp_path, evidence), ROOT)
    assert result["recordings"] == 6
    assert result["source_linked_segments"] >= 100
    assert result["asr_different_segments"] == 6
    assert "NOT_APPROVED" in result["status"]


def test_missing_manuscript_fails_closed(tmp_path, evidence):
    changed = dict(evidence)
    del changed["manuscripts/scientific-loop.txt"]
    with pytest.raises(ValueError, match="Missing release-review evidence"):
        verifier.verify(packaged(tmp_path, changed), ROOT)


def test_audio_tampering_is_rejected_even_if_checksum_inventory_is_updated(tmp_path, evidence):
    changed = dict(evidence)
    original = changed["UNREVIEWED-scientific-loop.mp3"]
    changed["UNREVIEWED-scientific-loop.mp3"] = b"X" + original[1:]
    with pytest.raises(ValueError, match="MP3/manuscript source identity"):
        verifier.verify(packaged(tmp_path, changed), ROOT)


def test_source_blind_transcript_must_match_exact_reference(tmp_path, evidence):
    changed = dict(evidence)
    report = json.loads(changed["ASR_AUDIT_UNREVIEWED.json"])
    report["chapters"][0]["segments"][0]["reference"] = "A different purported sentence"
    changed["ASR_AUDIT_UNREVIEWED.json"] = json.dumps(report).encode()
    with pytest.raises(ValueError, match="Source-linked speech segment mismatch"):
        verifier.verify(packaged(tmp_path, changed), ROOT)


def test_review_approval_template_must_be_unsigned(tmp_path, evidence):
    changed = dict(evidence)
    template = json.loads(changed["UNSIGNED-narration-approval.template.json"])
    template["authorize_release_candidate"] = True
    changed["UNSIGNED-narration-approval.template.json"] = json.dumps(template).encode()
    with pytest.raises(ValueError, match="preapproved review evidence"):
        verifier.verify(packaged(tmp_path, changed), ROOT)


def test_path_traversal_and_duplicate_names_fail_without_extracting(tmp_path, evidence):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("../private.txt", "secret")
    with pytest.raises(ValueError, match="Unsafe or duplicated ZIP path"):
        verifier.verify(archive, ROOT)
    with ZipFile(archive, "w") as z:
        z.writestr("duplicate.txt", "one")
        z.writestr("duplicate.txt", "two")
    with pytest.raises(ValueError, match="Unsafe or duplicated ZIP path"):
        verifier.verify(archive, ROOT)



def test_review_filter_must_show_all_asr_discrepancies(tmp_path, evidence):
    """A filtered review that hides orthographic variants cannot reach release."""
    import re
    changed = dict(evidence)
    html = changed["review.html"].decode("utf-8")
    flags = json.loads(re.search(
        r'<script id="asrData" type="application/json">([\s\S]*?)</script>', html
    ).group(1))
    flags["forward-science"] = []
    changed["review.html"] = re.sub(
        r'(<script id="asrData" type="application/json">)[\s\S]*?(</script>)',
        lambda match: match.group(1) + json.dumps(flags) + match.group(2),
        html,
    ).encode()
    with pytest.raises(ValueError, match="omits, changes, or misclassifies ASR differences"):
        verifier.verify(packaged(tmp_path, changed), ROOT)


def test_orthographic_variants_are_explicit_review_items(tmp_path, evidence):
    """Split/join-only ASR differences remain in the reviewer's filtered queue."""
    import re
    changed = dict(evidence)
    report = json.loads(changed["ASR_AUDIT_UNREVIEWED.json"])
    sample = report["chapters"][0]["segments"][0]
    sample["mismatches"] = [{
        "operation": "replace", "reference": "first hand",
        "recognized": "firsthand",
    }]
    changed["ASR_AUDIT_UNREVIEWED.json"] = json.dumps(report).encode()
    html = changed["review.html"].decode("utf-8")
    flags = json.loads(re.search(
        r'<script id="asrData" type="application/json">([\s\S]*?)</script>', html
    ).group(1))
    flags[report["chapters"][0]["slug"]][0]["discrepancies"] = sample["mismatches"]
    flags[report["chapters"][0]["slug"]][0]["difference_type"] = "orthography-only"
    changed["review.html"] = re.sub(
        r'(<script id="asrData" type="application/json">)[\s\S]*?(</script>)',
        lambda match: match.group(1) + json.dumps(flags) + match.group(2),
        html,
    ).encode()
    result = verifier.verify(packaged(tmp_path, changed), ROOT)
    assert result["asr_different_segments"] == 6
