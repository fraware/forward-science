"""Verify that published discovery metadata matches the source-verified essays."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forward_science_build_discovery", ROOT / "scripts" / "build.py")
assert spec and spec.loader
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

BASE = "https://example.org/forward-science"
ATOM = "{http://www.w3.org/2005/Atom}"


def _graph(page: Path) -> list[dict]:
    """Parse the unique JSON-LD graph in one fully published HTML page."""
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    script = soup.select_one('script[type="application/ld+json"]')
    assert script is not None
    payload = json.loads(script.string)
    assert payload["@context"] == "https://schema.org"
    return payload["@graph"]


def _node(graph: list[dict], kind: str) -> dict:
    matching = [node for node in graph if node["@type"] == kind]
    assert len(matching) == 1, f"Expected one {kind} node"
    return matching[0]


def test_published_graphs_and_agent_index_are_source_grounded(tmp_path: Path) -> None:
    """Six articles, author identity, original links, and dates must agree."""
    output = tmp_path / "site"
    essays = build.build(ROOT, output, BASE, strict=True)
    root = BASE + "/"
    home = BeautifulSoup((output / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert home.title.string == "Forward Science"
    assert "forward-deployed scientists" in home.select_one('meta[name="description"]')["content"].lower()
    assert home.select_one('link[type="application/atom+xml"]')["href"] == "feed.xml"
    collection_graph = _graph(output / "index.html")
    assert _node(collection_graph, "CollectionPage")["url"] == root
    assert _node(collection_graph, "CreativeWorkSeries")["@id"] == root + "#series"
    assert _node(collection_graph, "CreativeWorkSeries")["sameAs"] == "https://mateopetel.substack.com/t/forward-science"
    author = _node(collection_graph, "Person")
    assert author["url"] == "https://mateopetel.xyz/"
    assert "https://mateopetel.substack.com/" in author["sameAs"]
    assert "https://github.com/fraware" in author["sameAs"]
    items = _node(collection_graph, "ItemList")["itemListElement"]
    assert [item["position"] for item in items] == list(range(1, 7))

    guide = (output / "llms.txt").read_text(encoding="utf-8")
    assert "Forward-deployed scientist / deployed scientist" in guide
    assert guide.count("Original publication:") == 6
    assert "https://mateopetel.substack.com/t/forward-science" in guide
    for essay in essays:
        canonical = root + essay["slug"] + "/"
        assert canonical in guide
        assert essay["original_url"] in guide
        page = output / essay["slug"] / "index.html"
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert soup.title.string == "Forward Science"
        assert soup.select_one('link[rel="canonical"]')["href"] == canonical
        assert soup.select_one('meta[name="description"]')["content"] == essay["summary"]
        graph = _graph(page)
        article = _node(graph, "Article")
        assert article["@id"] == canonical + "#article"
        assert article["headline"] == essay["title"]
        assert article["datePublished"] == essay["date"]
        assert article["isBasedOn"]["url"] == essay["original_url"]
        assert article["author"]["@id"] == root + "#author"
        assert "dateModified" not in article
        assert len(article["about"]) >= 3
        crumbs = _node(graph, "BreadcrumbList")["itemListElement"]
        assert crumbs[0]["item"] == root
        assert crumbs[1]["item"] == canonical


def test_atom_feed_contains_exact_original_publication_timestamps(tmp_path: Path) -> None:
    output = tmp_path / "feed-site"
    essays = build.build(ROOT, output, BASE, strict=True)
    feed = ElementTree.parse(output / "feed.xml").getroot()
    entries = feed.findall(ATOM + "entry")
    assert len(entries) == 6
    provenance = json.loads((ROOT / "content" / "import-provenance.json").read_text(encoding="utf-8"))
    stamps = {record["slug"]: record["source_date_raw"] for record in provenance}
    by_url = {entry.findtext(ATOM + "id"): entry for entry in entries}
    for essay in essays:
        url = BASE + "/" + essay["slug"] + "/"
        entry = by_url[url]
        assert entry.findtext(ATOM + "published") == stamps[essay["slug"]]
        assert entry.findtext(ATOM + "updated") == stamps[essay["slug"]]
        links = entry.findall(ATOM + "link")
        assert any(link.get("href") == url and link.get("rel") == "alternate" for link in links)
        assert any(link.get("href") == essay["original_url"] and
                   link.get("rel") == "related" for link in links)


def test_preview_does_not_emit_published_edition_discovery_assets(tmp_path: Path) -> None:
    """Unimported placeholders must not receive authoritative content metadata."""
    import shutil

    source = tmp_path / "preview"
    (source / "content").mkdir(parents=True)
    shutil.copytree(ROOT / "templates", source / "templates")
    for name in ("essays.json", "landmarks.json", "audio.json"):
        shutil.copy2(ROOT / "content" / name, source / "content" / name)
    for name in ("styles.css", "favicon.svg", "reader.js"):
        shutil.copy2(ROOT / name, source / name)
    output = tmp_path / "preview-output"
    output.mkdir()
    # An incremental preview build must withdraw stale discovery files.
    for name in ("llms.txt", "feed.xml"):
        (output / name).write_text("stale", encoding="utf-8")
    build.build(source, output, BASE, strict=False)
    for name in ("llms.txt", "feed.xml", "sitemap.xml", "robots.txt"):
        assert not (output / name).exists()
    home = BeautifulSoup((output / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert home.select_one('script[type="application/ld+json"]') is None
    essay = BeautifulSoup((output / "forward-science" / "index.html").read_text(encoding="utf-8"), "html.parser")
    assert essay.select_one('meta[name="robots"]')["content"] == "noindex,follow"
    assert essay.select_one('script[type="application/ld+json"]') is None
