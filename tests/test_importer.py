"""Importer tests use synthetic text; no user export is needed in CI."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "import_substack.py"
spec = importlib.util.spec_from_file_location("forward_science_import", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic_post() -> str:
    sentences = [
        "The scientific loop connects a defensible question to measurement and subsequent action."
        for _ in range(55)
    ]
    return "<div>" + "".join("<p>" + " ".join(sentences[i:i+2]) + "</p>" for i in range(0, len(sentences), 2)) + "<p><a href='https://example.org/paper'>Reference</a>.</p></div>"


def make_synthetic_export(tmp_path: Path) -> Path:
    essays = json.loads((ROOT / "content" / "essays.json").read_text(encoding="utf-8"))
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["post_id", "title", "post_date", "is_published"])
    writer.writeheader()
    archive_path = tmp_path / "mock-export.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for n, essay in enumerate(essays, start=100):
            writer.writerow({"post_id": n, "title": essay["title"], "post_date": essay["date"], "is_published": "true"})
            archive.writestr(f"publication/posts/{n}.{essay['slug']}.html", synthetic_post())
        archive.writestr("publication/posts.csv", csv_buffer.getvalue())
        archive.writestr("publication/email_list.private.csv", "email\nsecret@example.com\n")
    return archive_path


def test_importer_requires_evidence_and_never_copies_subscribers(tmp_path: Path) -> None:
    archive = make_synthetic_export(tmp_path)
    test_root = tmp_path / "project"
    (test_root / "content").mkdir(parents=True)
    (test_root / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    previews = module.run(archive, test_root, apply=False)
    assert len(previews) == 6
    assert not list((test_root / "content").glob("essays/*.html"))
    imported = module.run(archive, test_root, apply=True)
    assert len(imported) == 6
    assert len(list((test_root / "content" / "essays").glob("*.html"))) == 6
    assert "secret@example.com" not in (test_root / "content" / "import-provenance.json").read_text()
    assert all(e["source_word_count"] >= 300 for e in imported)


def test_sanitization_blocks_executable_markup_and_preserves_text() -> None:
    html = synthetic_post().replace("<div>", "<div><script>alert(0)</script><img src='javascript:alert(1)' onerror='alert(2)' alt='figure'>")
    cleaned, info = module.clean_article_html(html)
    assert "<script" not in cleaned
    assert "onerror=" not in cleaned
    assert "javascript:" not in cleaned
    assert "Reference" in cleaned
    assert info["source_word_count"] >= 300


def test_sanitization_rejects_truncated_article() -> None:
    with pytest.raises(ValueError, match="short"):
        module.clean_article_html("<p>Too short to be a published essay.</p>")


def test_ambiguous_title_fails() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        module.match_row([{"title": "Forward Science"}, {"title": "Forward Science"}], "Forward Science")


def test_end_to_end_export_to_full_site(tmp_path: Path) -> None:
    """Complete, sanitized articles must render in indexable local reading pages."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from build import build

    dest = tmp_path / "project"
    (dest / "content").mkdir(parents=True)
    (dest / "templates").mkdir()
    for name in ("essays.json",):
        (dest / "content" / name).write_bytes((ROOT / "content" / name).read_bytes())
    for template in (ROOT / "templates").iterdir():
        (dest / "templates" / template.name).write_bytes(template.read_bytes())
    for asset in ("styles.css", "favicon.svg", "reader.js", "device-narration.js"):
        (dest / asset).write_bytes((ROOT / asset).read_bytes())
    for name in ("landmarks.json", "audio.json"):
        (dest / "content" / name).write_bytes((ROOT / "content" / name).read_bytes())
    archive = make_synthetic_export(tmp_path)
    run_import = module.run(archive, dest, apply=True)
    assert len(run_import) == 6
    out = dest / "site"
    essays = build(dest, out, "https://forward.example.org", strict=True)
    assert len(essays) == 6 and all(e["complete"] for e in essays)
    from bs4 import BeautifulSoup
    page = BeautifulSoup((out / "scientific-loop" / "index.html").read_text(), "html.parser")
    assert len(page.select('article[aria-label="Full essay"] p')) >= 3
    assert page.select_one('meta[name="robots"]') is None
    assert page.select_one('link[rel="canonical"]')["href"] == "https://forward.example.org/scientific-loop/"
    sitemap = (out / "sitemap.xml").read_text()
    assert sitemap.count("<loc>") == 7
    assert "forward.example.org" in (out / "robots.txt").read_text()


def test_privacy_reduced_author_export(tmp_path: Path) -> None:
    """User-shareable archive contains exactly six texts and no subscriber data."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from prepare_private_export import select_essays

    complete = make_synthetic_export(tmp_path)
    minimal = tmp_path / "forward-science-only.zip"
    select_essays(complete, minimal)
    with zipfile.ZipFile(minimal) as z:
        assert len(z.namelist()) == 7
        assert "posts.csv" in z.namelist()
        assert all(x.endswith(".html") or x == "posts.csv" for x in z.namelist())
        assert not any("private" in x or "email" in x for x in z.namelist())
    temp_root = tmp_path / "project_minimal"
    (temp_root / "content").mkdir(parents=True)
    (temp_root / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    assert len(module.run(minimal, temp_root, apply=True)) == 6


def test_strict_build_detects_changed_imported_text(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from build import build
    dest = tmp_path / "project"
    (dest / "content").mkdir(parents=True)
    (dest / "templates").mkdir()
    (dest / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    for t in (ROOT / "templates").iterdir():
        (dest / "templates" / t.name).write_bytes(t.read_bytes())
    for a in ("styles.css", "favicon.svg", "reader.js", "device-narration.js"):
        (dest / a).write_bytes((ROOT / a).read_bytes())
    for name in ("landmarks.json", "audio.json"):
        (dest / "content" / name).write_bytes((ROOT / "content" / name).read_bytes())
    module.run(make_synthetic_export(tmp_path), dest, apply=True)
    body = dest / "content" / "essays" / "forward-science.html"
    body.write_text(body.read_text(encoding="utf-8") + "<p>Modified after validation.</p>")
    with pytest.raises(ValueError, match="modified since verification"):
        build(dest, dest / "site", "https://example.org", strict=True)


def test_dotted_substack_post_ids_match_export_member(tmp_path: Path) -> None:
    """The live author export stores ``id.slug`` in the post_id column."""
    archive_path = tmp_path / "export.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("posts/202156599.forward-science.html", synthetic_post())
        archive.writestr("posts/202156600.other-title.html", synthetic_post())
    with zipfile.ZipFile(archive_path) as archive:
        assert module.find_html(archive, {"post_id": "202156599.forward-science"}) == "posts/202156599.forward-science.html"
        assert module.find_html(archive, {"post_id": "202156599"}) == "posts/202156599.forward-science.html"
        with pytest.raises(ValueError, match="malformed"):
            module.find_html(archive, {"post_id": "../../other"})


def test_readonly_compare_export_detects_drift(tmp_path: Path) -> None:
    """A fresh official export is compared without touching committed sources."""
    archive = make_synthetic_export(tmp_path)
    dest = tmp_path / "project_compare"
    (dest / "content").mkdir(parents=True)
    (dest / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    module.run(archive, dest, apply=True)
    matches = module.run(archive, dest, apply=False, compare=True)
    assert len(matches) == 6
    assert all(all(entry["edition_comparison"].values()) for entry in matches)
    body = dest / "content" / "essays" / "forward-science.html"
    previous = body.read_bytes()
    body.write_bytes(previous.replace(b"scientific loop", b"scientific workflow", 1))
    changed = body.read_bytes()
    report = module.run(archive, dest, apply=False, compare=True)
    assert report[0]["edition_comparison"]["sanitized_html"] is False
    assert report[0]["edition_comparison"]["source_sha256"] is True
    assert all(all(entry["edition_comparison"].values()) for entry in report[1:])
    assert body.read_bytes() == changed  # read-only, even when differences exist


def test_readonly_compare_export_detects_provenance_change(tmp_path: Path) -> None:
    archive = make_synthetic_export(tmp_path)
    dest = tmp_path / "project_metadata"
    (dest / "content").mkdir(parents=True)
    (dest / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    module.run(archive, dest, apply=True)
    path = dest / "content" / "import-provenance.json"
    records = json.loads(path.read_text())
    records[0]["source_post_id"] = "unexpected.post-id"
    path.write_text(json.dumps(records), encoding="utf-8")
    report = module.run(archive, dest, apply=False, compare=True)
    assert report[0]["edition_comparison"]["sanitized_html"] is True
    assert report[0]["edition_comparison"]["source_post_id"] is False
