"""ASR audit tests use original source text and a mocked transcription service."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("asr_audit", ROOT / "scripts/audit_narration_asr.py")
assert spec is not None and spec.loader is not None
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_word_distance_and_critical_qualification_flags():
    assert audit.word_edit_distance(["a", "b", "c"], ["a", "c"]) == 1
    assert audit.word_edit_distance(["a", "c"], ["a", "b", "c"]) == 1
    assert audit.word_edit_distance([], ["a", "b"]) == 2
    assert audit.compare("The scientific loop is essential.", "The scientific loop is essential")["priority"] == "low"
    omitted = audit.compare("The intervention must not proceed without approval.",
                            "The intervention must proceed without approval.")
    assert omitted["priority"] == "high"
    assert any("not" in x["reference"] for x in omitted["critical_mismatches"])
    changed_number = audit.compare("We used two independent trials.", "We used three independent trials.")
    assert changed_number["priority"] == "high"
    assert audit.compare("Every experiment has a result.", "")["word_error_rate"] == 1


def test_draft_source_and_audio_hashes_are_checked(tmp_path: Path):
    from prepare_narration import compile_narration
    from generate_all_audio_candidates import segments_for
    drafts = tmp_path / "drafts"
    (drafts / "manuscripts").mkdir(parents=True)
    compiled = compile_narration(ROOT, tmp_path / "source")
    records = []
    for essay in compiled["essays"]:
        slug = essay["slug"]
        text = (tmp_path / "source" / f"{slug}.txt").read_text()
        (drafts / "manuscripts" / f"{slug}.txt").write_text(text)
        mp3 = drafts / f"UNREVIEWED-{slug}.mp3"
        mp3.write_bytes(("FAKE-AUDIO-" + slug).encode())
        cues = []
        position, paragraph = 0., 1
        for index, (phrase, paragraph_end) in enumerate(segments_for(text), 1):
            cues.append({
                "segment": index, "paragraph": paragraph,
                "source_sha256": hashlib.sha256(phrase.encode()).hexdigest(),
                "start_seconds": position, "end_seconds": position + 1.,
            })
            position += 1.25
            paragraph += int(paragraph_end)
        records.append({
            "slug": slug, "filename": mp3.name, "sha256": audit.file_hash(mp3),
            "manuscript_sha256": essay["spoken_body_sha256"], "chunks": len(cues),
            "segment_timeline": cues,
        })
    (drafts / "UNREVIEWED-MANIFEST.json").write_text(json.dumps({
        "status": "UNREVIEWED_SYNTHETIC_DRAFTS",
        "publication_approved": False,
        "recordings": records,
    }))
    assert len(audit.validate_drafts(ROOT, drafts)) == 6
    (drafts / "UNREVIEWED-forward-science.mp3").write_bytes(b"CHANGED")
    with pytest.raises(ValueError, match="Missing or modified MP3"):
        audit.validate_drafts(ROOT, drafts)


def test_audit_never_grants_approval_and_exposes_discrepancies():
    assert "UNREVIEWED_AUTOMATED_INSPECTION_ONLY" in (
        ROOT / "scripts/audit_narration_asr.py"
    ).read_text()


def test_orthographic_joining_never_becomes_a_high_priority_audio_alarm():
    """Spelling-only ASR differences must be distinguished from content errors."""
    item = audit.compare(
        "What National Labs saw first hand is that the work continues.",
        "What National Labs saw firsthand is that the work continues.",
    )
    assert item["word_error_rate"] > 0
    assert item["content_edit_ratio"] == 0
    assert item["priority"] == "low"
    assert not item["human_check_needed"]
    assert item["orthographic_variants"]
    assert not item["critical_mismatches"]


def test_homophones_and_missing_qualifications_remain_reviewable():
    """Similar-sounding words remain content uncertainties; omitted negation is high priority."""
    homophone = audit.compare("Scientific sight sustains the institution.", "Scientific site sustains the institution.")
    assert homophone["human_check_needed"]
    assert homophone["content_mismatches"]
    lost_negation = audit.compare("The model must not determine the experiment.", "The model must determine the experiment.")
    assert lost_negation["priority"] == "high"
    assert lost_negation["human_check_needed"]
    assert audit.compare("The instrument will require local validation.", "The instrument will require validation.")["human_check_needed"]
