"""Distribution editions are generated from the checksum-verified six essays."""
from __future__ import annotations

import importlib.util
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forward_science_exports", ROOT / "scripts/export_editions.py")
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def test_complete_editions_are_valid_and_linked(tmp_path: Path) -> None:
    """The static output includes complete, navigable PDF, EPUB, and Markdown."""
    result = exporter.build(ROOT, tmp_path, "https://example.org/site")
    assert {p.suffix for p in result} == {".epub", ".pdf", ".md"}
    md = (tmp_path / "forward-science.md").read_text(encoding="utf-8")
    for item in exporter.chapters(ROOT):
        assert f'## {item["number"]} · {item["title"]}' in md
        assert f'https://example.org/site/{item["slug"]}/' in md
    assert "Subscribe now" not in md
    assert (tmp_path / "forward-science.pdf").read_bytes().startswith(b"%PDF-")
    assert (tmp_path / "forward-science.pdf").stat().st_size > 40000

    with zipfile.ZipFile(tmp_path / "forward-science.epub") as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/epub+zip"
        nav = BeautifulSoup(archive.read("EPUB/nav.xhtml"), "html.parser")
        assert len(nav.find_all("li")) == 6
        for essay in exporter.chapters(ROOT):
            xhtml = archive.read(f'EPUB/{essay["slug"]}.xhtml')
            ET.fromstring(xhtml)
            soup = BeautifulSoup(xhtml, "html.parser")
            paragraphs = soup.find_all("p")
            assert len(paragraphs) >= 12
            assert "Subscribe now" not in soup.get_text(" ", strip=True)
            assert essay["soup"].find("p").get_text(" ", strip=True) in soup.get_text(" ", strip=True)


def test_source_hash_validation_prevents_corrupt_exports(tmp_path: Path) -> None:
    """An altered author text fails before building any format."""
    shutil.copytree(ROOT / "content", tmp_path / "content")
    path = tmp_path / "content/essays/forward-science.html"
    path.write_text(path.read_text(encoding="utf-8") + "<p>tampered</p>", encoding="utf-8")
    with pytest.raises(ValueError, match="provenance mismatch"):
        exporter.build(tmp_path, tmp_path / "downloads")
    assert not (tmp_path / "downloads/forward-science.pdf").exists()


def test_export_is_deterministic(tmp_path: Path) -> None:
    """Generated public artifacts have stable bytes for identical source data."""
    import hashlib
    a, b = tmp_path / "one", tmp_path / "two"
    first, second = exporter.build(ROOT, a), exporter.build(ROOT, b)
    assert [hashlib.sha256(x.read_bytes()).hexdigest() for x in first] == [
        hashlib.sha256(x.read_bytes()).hexdigest() for x in second
    ]
