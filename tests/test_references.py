"""Deterministic reference audit tests using local, immutable article sources."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reference_audit", ROOT / "scripts/audit_references.py")
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_full_six_essay_reference_inventory_matches_original_import():
    report = audit.build_inventory(ROOT)
    assert report["schema_version"] == 1
    assert report["essays"] == {
        "forward-science": 10,
        "forward-deployed-scientists": 9,
        "scientific-loop": 4,
        "extension-agents": 17,
        "political-economy": 0,
        "future-laboratory": 6,
    }
    assert report["citation_count"] == 46
    assert report["distinct_external_urls"] == 32
    assert report["excluded_subscription_footers"] == 6
    assert len(report["citations"]) == report["citation_count"]
    assert all(x["kind"] == "external" and x["host"] for x in report["citations"])
    assert all(x["paragraph"] is not None for x in report["citations"])


def test_paragraph_number_and_context_remain_aligned_with_rendered_reader():
    report = audit.build_inventory(ROOT)
    result = [x for x in report["citations"] if x["label"] == "sequencing core"]
    assert len(result) == 1
    assert result[0]["slug"] == "extension-agents"
    assert result[0]["paragraph"] == 8
    assert "beamline" in result[0]["context"]
    assert result[0]["url"].endswith("/DNA-Sequencing-Costs-Data")


def test_no_citation_omitted_for_outer_paragraph_and_subscription_footer():
    html = (
        '<h2><a href="https://example.org/method">Method</a></h2>'
        '<p>Research <a href="https://example.org/result">result</a>.</p>'
        '<p><a href="https://mateopetel.substack.com/subscribe?">Subscribe now</a></p>'
    )
    entries, excluded = audit.scan_html("synthetic", html)
    assert len(entries) == 2 and len(excluded) == 1
    assert entries[0]["paragraph"] is None
    assert entries[1]["paragraph"] == 1
    assert entries[0]["context"] == ""


@pytest.mark.parametrize("href", [
    "javascript:alert(1)",
    "http://example.org/paper",
    "//example.org/paper",
    "https://username:password@example.org/",
    "https://example.org/a/../b",
    "",
])
def test_unsafe_or_ambiguous_urls_fail_closed(href: str):
    with pytest.raises(ValueError, match="Unrecognized or unsafe"):
        audit.classify_link(href)


def test_local_fragment_is_separately_classified():
    assert audit.classify_link("#references") == ("internal_fragment", "")


def test_empty_anchor_label_fails():
    with pytest.raises(ValueError, match="empty hyperlink label"):
        audit.scan_html("test", '<p><a href="https://example.org"></a></p>')


def test_subscription_footer_placed_in_middle_is_rejected():
    html = ('<p><a href="https://mateopetel.substack.com/subscribe?">Subscribe now</a></p>'
            '<p>The essay continues.</p>')
    with pytest.raises(ValueError, match="not the final paragraph"):
        audit.scan_html("test", html)


def test_article_drift_fails_source_hash_gate(tmp_path: Path):
    (tmp_path / "content" / "essays").mkdir(parents=True)
    for path in ("essays.json", "import-provenance.json"):
        shutil.copy2(ROOT / "content" / path, tmp_path / "content" / path)
    for html in (ROOT / "content" / "essays").glob("*.html"):
        shutil.copy2(html, tmp_path / "content" / "essays" / html.name)
    path = tmp_path / "content" / "essays" / "future-laboratory.html"
    path.write_text(path.read_text(encoding="utf-8") + "<p>Altered essay</p>", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from recorded SHA-256"):
        audit.build_inventory(tmp_path)


def test_missing_manifest_record_fails_closed(tmp_path: Path):
    (tmp_path / "content").mkdir()
    records = json.loads((ROOT / "content" / "essays.json").read_text())
    (tmp_path / "content" / "essays.json").write_text(json.dumps(records[:-1]))
    (tmp_path / "content" / "import-provenance.json").write_bytes(
        (ROOT / "content" / "import-provenance.json").read_bytes())
    with pytest.raises(ValueError, match="exactly six essays"):
        audit.build_inventory(tmp_path)
