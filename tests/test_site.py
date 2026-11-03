"""Structural tests for the generated static publication."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build.py"
spec = importlib.util.spec_from_file_location("forward_science_build", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_six_articles_and_canonical_metadata() -> None:
    essays = module.load_essays(ROOT)
    assert len(essays) == 6
    assert essays[0]["slug"] == "forward-science"
    assert essays[-1]["slug"] == "future-laboratory"
    assert [e["number"] for e in essays] == [f"{i:02d}" for i in range(6)]
    assert essays[1]["date"] > essays[2]["date"]  # declared order differs from publication dates
    assert essays[0]["date_long"] == "June 22, 2026"


def preview_root(tmp_path: Path) -> Path:
    """Construct a source checkout with metadata but no imported articles."""
    root = tmp_path / "unimported"
    (root / "content").mkdir(parents=True)
    (root / "templates").mkdir()
    (root / "content" / "essays.json").write_bytes((ROOT / "content" / "essays.json").read_bytes())
    for template in (ROOT / "templates").iterdir():
        (root / "templates" / template.name).write_bytes(template.read_bytes())
    for asset in ("styles.css", "favicon.svg"):
        (root / asset).write_bytes((ROOT / asset).read_bytes())
    return root


def test_preview_build_has_no_false_full_text_claims(tmp_path: Path) -> None:
    root = preview_root(tmp_path)
    out = tmp_path / "site"
    module.build(root, out, None)
    home = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert len(home.select("ol.essay-list > li")) == 6
    assert home.select_one("h1").get_text(" ", strip=True) == "Forward Science"
    for essay in module.load_essays(root):
        page = out / essay["slug"] / "index.html"
        assert page.is_file()
        parsed = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert parsed.select_one('meta[name="robots"]')["content"] == "noindex,follow"
        assert parsed.select_one('link[rel="canonical"]')["href"] == essay["original_url"]
        assert parsed.select_one('a.source-action')["href"] == essay["original_url"]
        assert not parsed.select_one('article[aria-label="Full essay"]')
    assert not (out / "sitemap.xml").exists()


def test_strict_fails_until_all_originals_are_present(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="incomplete chapters"):
        module.build(preview_root(tmp_path), tmp_path / "strict", "https://example.org", strict=True)


def test_strict_build_accepts_full_verified_export(tmp_path: Path) -> None:
    essays = module.build(ROOT, tmp_path / "full", "https://example.org", strict=True)
    assert len(essays) == 6
    assert all(essay["complete"] for essay in essays)
    for essay in essays:
        page = BeautifulSoup((tmp_path / "full" / essay["slug"] / "index.html").read_text(), "html.parser")
        assert page.select_one('article[aria-label="Full essay"]')
        assert not page.select_one('meta[name="robots"]')
        assert page.select_one('link[rel="canonical"]')["href"] == f"https://example.org/{essay['slug']}/"


def test_base_url_validation() -> None:
    assert module.verify_base_url("https://example.org/site/") == "https://example.org/site"
    for value in ("http://example.org", "//example.org", "https://example.org/x/../y", "https://example.org/?a=1", "https://user:pass@example.org"):
        with pytest.raises(ValueError):
            module.verify_base_url(value)


def test_no_broken_local_routes(tmp_path: Path) -> None:
    out = tmp_path / "site"
    module.build(ROOT, out, None)
    for page in out.rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.find_all("a", href=True):
            url = link["href"].split("#", 1)[0]
            if not url or url.startswith(("http://", "https://", "mailto:")):
                continue
            local = (page.parent / url)
            resolved = local / "index.html" if local.is_dir() else local
            assert resolved.is_file(), f"Broken link in {page}: {link['href']}"
