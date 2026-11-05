"""No narrated-release artifact is created without concrete signed review evidence."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("stage_reviewed_audio", ROOT / "scripts/stage_reviewed_audio.py")
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def setup(tmp_path):
    from prepare_narration import compile_narration
    compiled = compile_narration(ROOT, tmp_path / "source")
    folder = tmp_path / "drafts"
    (folder / "manuscripts").mkdir(parents=True)
    rows, chapters, reviews = [], [], []
    for item in compiled["essays"]:
        slug = item["slug"]
        src = (tmp_path / "source" / (slug + ".txt")).read_bytes()
        (folder / "manuscripts" / (slug + ".txt")).write_bytes(src)
        data = ("INERT TEST MP3 " + slug).encode() * 7000
        mp3 = folder / f"UNREVIEWED-{slug}.mp3"
        mp3.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        rows.append({"slug": slug, "filename": mp3.name, "sha256": sha,
                     "manuscript_sha256": hashlib.sha256(src).hexdigest(), "chunks": 2})
        chapters.append({"slug": slug, "segments": [
            {"segment": 1, "mismatch_count": 1}, {"segment": 2, "mismatch_count": 0},
        ]})
        reviews.append({"slug": slug, "sha256": sha, "manuscript_sha256": rows[-1]["manuscript_sha256"],
                        "segment_count": 2, "notes": {
                            "__fullListened": True, "1": {"status": "checked", "note": "Listened against source, ASR mistake"},
                        }})
    manifest = folder / "UNREVIEWED-MANIFEST.json"
    manifest.write_text(json.dumps({"status": "UNREVIEWED_SYNTHETIC_DRAFTS",
                                    "publication_approved": False, "voice": "af_heart", "recordings": rows}))
    asr = tmp_path / "ASR.json"
    asr.write_text(json.dumps({"publication_approved": False,
                               "source_manifest_sha256": stage.digest(manifest), "chapters": chapters}))
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"kind": "UNREVIEWED_NARRATION_WORKING_NOTES",
                                 "publication_approved": False, "recordings": reviews}))
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"authorize_release_candidate": True, "reviewer": "Fixture Reviewer",
                                    "reviewed_on": date.today().isoformat(),
                                    "voice": {"type": "synthetic", "name": "af_heart",
                                              "provider": "Kokoro test", "distribution_rights_basis": "TEST ONLY"},
                                    "attestations": {k: True for k in stage.FLAGS}}))
    return folder, asr, notes, approval


def test_staged_output_only_with_explicit_complete_review(tmp_path):
    drafts, report, notes, approval = setup(tmp_path)
    target = tmp_path / "staged"
    stage.stage(ROOT, drafts, report, notes, approval, target, validator=lambda _: None)
    assert len(list((target / "media").glob("*.mp3"))) == 6
    assert len(json.loads((target / "audio.json").read_text())) == 6
    assert json.loads((target / "RELEASE-RECEIPT.json").read_text())["published"] is False


@pytest.mark.parametrize("failure", ["missing_listen", "unreviewed_flag", "unresolved_problem",
                                     "wrong_audio", "wrong_asr", "no_signoff", "rights"])
def test_rejects_incomplete_or_false_release_evidence(tmp_path, failure):
    drafts, report, notes, approval = setup(tmp_path)
    if failure in ("missing_listen", "unreviewed_flag", "unresolved_problem"):
        obj = json.loads(notes.read_text())
        one = obj["recordings"][0]["notes"]
        if failure == "missing_listen":
            one["__fullListened"] = False
        if failure == "unreviewed_flag":
            one["1"]["status"] = "unreviewed"
        if failure == "unresolved_problem":
            one["2"] = {"status": "problem", "note": "Wrong pronunciation"}
        notes.write_text(json.dumps(obj))
    if failure == "wrong_audio":
        (drafts / "UNREVIEWED-forward-science.mp3").write_bytes(b"tampered")
    if failure == "wrong_asr":
        obj = json.loads(report.read_text())
        obj["source_manifest_sha256"] = "f" * 64
        report.write_text(json.dumps(obj))
    if failure in ("no_signoff", "rights"):
        obj = json.loads(approval.read_text())
        if failure == "no_signoff":
            obj["authorize_release_candidate"] = False
        else:
            obj["attestations"]["distribution_rights_confirmed"] = False
        approval.write_text(json.dumps(obj))
    with pytest.raises(ValueError):
        stage.stage(ROOT, drafts, report, notes, approval, tmp_path / "staged",
                    validator=lambda _: None)
    assert not (tmp_path / "staged").exists()
