"""Network-free regression tests for independent public-edition comparisons."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_live_substack.py"
spec = importlib.util.spec_from_file_location("audit_live_substack", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


SLUGS = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")


def article_html(*, link="https://example.org/paper", amended=False, subscribe=True):
    paragraphs = [f"Research paragraph {i} records evidence, methods and scientific judgment "
                  "as part of the test corpus for this publication."
                  for i in range(1, 7)]
    if amended:
        paragraphs[2] = paragraphs[2].replace("methods", "altered methods")
    paragraphs[4] += f' <a href="{link}">Primary reference</a>'
    html = "".join(f"<p>{p}</p>" for p in paragraphs)
    if subscribe:
        html += '<p><a href="https://mateopetel.substack.com/subscribe?">Subscribe now</a></p>'
    return html


def fixture(tmp_path: Path):
    root = tmp_path / "repository"
    (root / "content" / "essays").mkdir(parents=True)
    manifest = []
    provenance = []
    posts = {}
    for i, slug in enumerate(SLUGS):
        number = str(60000000 + i)
        e = {"slug": slug, "title": f"Chapter {slug}",
             "subtitle": f"Scientific subtitle {slug}",
             "original_url": f"https://mateopetel.substack.com/p/{slug}",
             "date": "2026-06-22"}
        manifest.append(e)
        provenance.append({"slug": slug, "source_post_id": f"{number}.{slug}"})
        (root / "content" / "essays" / f"{slug}.html").write_text(article_html(), encoding="utf-8")
        posts[slug] = {"id": int(number), "slug": slug, "title": e["title"],
                       "subtitle": e["subtitle"], "post_date": "2026-06-22T16:30:00.000Z",
                       "body_html": article_html(subscribe=False)}
    (root / "content" / "essays.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "content" / "import-provenance.json").write_text(json.dumps(provenance), encoding="utf-8")

    def public_fetch(url):
        slug = url.rsplit("/", 1)[-1]
        return posts[slug]

    return root, manifest, provenance, posts, public_fetch


def test_six_public_originals_match_even_if_subscription_footer_differs(tmp_path: Path):
    root, _manifest, _provenance, _posts, fetch = fixture(tmp_path)
    results = module.audit_all(root, fetch)
    assert len(results) == 6
    assert all(item["status"] == "match" for item in results)
    assert all(item["export_paragraphs"] == 6 for item in results)
    assert all(item["export_fingerprint"] == item["live_fingerprint"] for item in results)


def test_changed_paragraph_is_source_drift(tmp_path: Path):
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"]["body_html"] = article_html(amended=True)
    result = module.audit_one(manifest[0], provenance[0], root, fetch)
    assert result["status"] == "drift"
    assert result["first_difference"]["paragraph"] == 3
    assert result["export_fingerprint"] != result["live_fingerprint"]


def test_changed_reference_destination_is_source_drift(tmp_path: Path):
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"]["body_html"] = article_html(link="https://example.org/other", subscribe=False)
    result = module.audit_one(manifest[0], provenance[0], root, fetch)
    assert result["status"] == "drift"
    assert result["first_link_difference"] == 1
    assert "citation hyperlinks" in result["reason"]


@pytest.mark.parametrize("field,value", [("title", "Other Title"), ("subtitle", "Other subtitle")])
def test_changed_public_metadata_is_source_drift(tmp_path: Path, field: str, value: str):
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"][field] = value
    assert module.audit_one(manifest[0], provenance[0], root, fetch)["status"] == "drift"


def test_wrong_post_identity_is_unavailable_not_match(tmp_path: Path):
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"]["id"] = 3
    result = module.audit_one(manifest[0], provenance[0], root, fetch)
    assert result["status"] == "unavailable"
    assert "ID" in result["reason"]


def test_short_or_missing_live_body_is_unavailable(tmp_path: Path):
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"]["body_html"] = "<p>Preview</p>"
    assert module.audit_one(manifest[0], provenance[0], root, fetch)["status"] == "unavailable"
    posts["alpha"].pop("body_html")
    assert module.audit_one(manifest[0], provenance[0], root, fetch)["status"] == "unavailable"


def test_transport_error_is_unavailable_not_match(tmp_path: Path):
    root, manifest, provenance, _posts, _fetch = fixture(tmp_path)
    def failing(_url):
        raise module.UnavailableSource("HTTP 429")
    result = module.audit_one(manifest[0], provenance[0], root, failing)
    assert result["status"] == "unavailable"
    assert "429" in result["reason"]


@pytest.mark.parametrize("url", [
    "http://mateopetel.substack.com/p/alpha",
    "https://evil.test/p/alpha",
    "https://mateopetel.substack.com/p/../alpha",
    "https://mateopetel.substack.com/p/alpha?code=token",
    "https://mateopetel.substack.com/p/alpha#frag",
])
def test_public_api_request_is_strictly_source_scoped(url: str):
    with pytest.raises(ValueError):
        module.post_api_url(url)


def test_mismatched_provenance_inventory_is_rejected(tmp_path: Path):
    root, _manifest, _provenance, _posts, fetch = fixture(tmp_path)
    provenance = json.loads((root / "content" / "import-provenance.json").read_text())
    provenance[3]["slug"] = "alpha"
    (root / "content" / "import-provenance.json").write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="same six distinct essays"):
        module.audit_all(root, fetch)


def test_text_normalization_preserves_content_differences():
    assert module.normalize_text("cafe\u0301    research") == "café research"
    assert module.normalize_text("The lab is safe.") != module.normalize_text("The lab is unsafe.")
    assert module.normalize_text("Experiment A") != module.normalize_text("experiment A")


def test_unexpected_html_markup_is_not_discarded_silently():
    body = '<p>First <strong>experiment</strong> succeeded.</p><h2>Conclusions</h2><p>Second.</p>'
    paragraphs, refs, full_text, media = module.article_evidence(body)
    assert paragraphs == ["First experiment succeeded.", "Conclusions", "Second."]
    assert "Conclusions" in full_text
    assert refs == []
    assert media == []


def test_nonparagraph_addition_and_media_changes_are_detected(tmp_path: Path):
    """A new heading or image cannot disappear from source-integrity evidence."""
    root, manifest, provenance, posts, fetch = fixture(tmp_path)
    posts["alpha"]["body_html"] += "<aside>Unexpected editorial correction.</aside>"
    result = module.audit_one(manifest[0], provenance[0], root, fetch)
    assert result["status"] == "drift"
    assert "Full article text" in result["reason"]

    posts["alpha"]["body_html"] = article_html(subscribe=False) + '<img src="new.png" alt="figure">'
    result = module.audit_one(manifest[0], provenance[0], root, fetch)
    assert result["status"] == "drift"
    assert result["live_media_count"] == 1
