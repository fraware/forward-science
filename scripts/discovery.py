#!/usr/bin/env python3
"""Build factual discovery metadata for the Forward Science essay collection.

This module describes the published corpus without modifying imported prose or
inventing revision dates, citations, endorsements, or third-party authority.
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

# Editorial descriptors grounded in the six original essay titles and summaries.
TOPICS = {
    "forward-science": ("Forward Science", "AI for science",
                        "scientific institutions", "forward-deployed scientists"),
    "forward-deployed-scientists": ("forward-deployed scientists",
                                   "scientist-builders", "research infrastructure"),
    "scientific-loop": ("scientific loop", "experimental validation",
                        "scientific judgment", "AI for science"),
    "extension-agents": ("scientific intermediaries", "agricultural extension",
                         "research software engineering", "forward-deployed scientists"),
    "political-economy": ("scientific capacity", "research funding",
                          "scientific workforce", "forward-deployed scientists"),
    "future-laboratory": ("laboratory automation", "self-driving laboratories",
                          "scientific evidence", "scientific judgment"),
}


def schemas(essays: list[dict], base_url: str) -> tuple[dict, dict[str, dict]]:
    """Return Schema.org collection and article graphs for published essays."""
    if set(TOPICS) != {e["slug"] for e in essays}:
        raise ValueError("Discovery subjects must match the entire essay manifest")
    root_url = base_url + "/"
    author_id = root_url + "#author"
    website_id = root_url + "#website"
    series_id = root_url + "#series"
    description = (
        "Six essays on Forward Science, forward-deployed scientists, "
        "scientific loops, and the institutions of AI-enabled discovery."
    )
    author = {
        "@type": "Person", "@id": author_id,
        "name": "Mateo H. Petel", "url": "https://mateopetel.xyz/",
        "sameAs": ["https://mateopetel.substack.com/",
                   "https://profiles.stanford.edu/mateo-petel",
                   "https://www.linkedin.com/in/mateo-petel/",
                   "https://github.com/fraware"],
    }
    website = {
        "@type": "WebSite", "@id": website_id, "url": root_url,
        "name": "Forward Science", "description": description,
        "inLanguage": "en", "publisher": {"@id": author_id},
    }
    series = {
        "@type": "CreativeWorkSeries", "@id": series_id,
        "url": root_url, "name": "Forward Science",
        "description": description, "inLanguage": "en",
        "creator": {"@id": author_id},
        "sameAs": "https://mateopetel.substack.com/t/forward-science",
        "hasPart": [{"@id": f"{root_url}{essay['slug']}/#article"} for essay in essays],
    }
    collection = {
        "@type": "CollectionPage", "@id": root_url + "#webpage",
        "url": root_url, "name": "Forward Science",
        "description": description, "inLanguage": "en",
        "isPartOf": {"@id": website_id},
        "mainEntity": {"@id": series_id},
    }
    contents = {
        "@type": "ItemList", "@id": root_url + "#contents",
        "name": "Forward Science essays",
        "itemListElement": [
            {
                "@type": "ListItem", "position": index,
                "item": {
                    "@type": "Article",
                    "@id": f"{root_url}{essay['slug']}/#article",
                    "name": essay["title"],
                    "url": f"{root_url}{essay['slug']}/",
                },
            }
            for index, essay in enumerate(essays, start=1)
        ],
    }
    overview = {"@context": "https://schema.org",
                "@graph": [author, website, series, collection, contents]}
    article_graphs = {}
    for essay in essays:
        url = f"{root_url}{essay['slug']}/"
        page_id = url + "#webpage"
        article_id = url + "#article"
        article_graphs[essay["slug"]] = {
            "@context": "https://schema.org",
            "@graph": [
                author, website,
                {
                    "@type": "WebPage", "@id": page_id, "url": url,
                    "name": essay["title"], "description": essay["summary"],
                    "inLanguage": "en", "isPartOf": {"@id": website_id},
                    "mainEntity": {"@id": article_id},
                    "breadcrumb": {"@id": url + "#breadcrumb"},
                },
                {
                    "@type": "Article", "@id": article_id, "url": url,
                    "headline": essay["title"], "description": essay["summary"],
                    "datePublished": essay["date"], "inLanguage": "en",
                    "author": {"@id": author_id},
                    "publisher": {"@id": author_id},
                    "isPartOf": {"@id": series_id},
                    "mainEntityOfPage": {"@id": page_id},
                    "isBasedOn": {"@type": "Article", "url": essay["original_url"]},
                    "about": [{"@type": "Thing", "name": term}
                              for term in TOPICS[essay["slug"]]],
                },
                {
                    "@type": "BreadcrumbList", "@id": url + "#breadcrumb",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1,
                         "name": "Forward Science", "item": root_url},
                        {"@type": "ListItem", "position": 2,
                         "name": essay["title"], "item": url},
                    ],
                },
            ],
        }
    return overview, article_graphs


def write_assets(root: Path, output: Path, base_url: str, essays: list[dict]) -> None:
    """Write an optional agent reading guide and an Atom publication feed.

    llms.txt is an experimental convention, not a ranking mechanism.
    Feed timestamps are taken from the author's original export provenance.
    """
    root_url = base_url + "/"
    guide = [
        "# Forward Science",
        "",
        "> Six essays by Mateo H. Petel on the institutions connecting AI, "
        "computation, automation, and scientific judgment with research.",
        "",
        "Read the [complete collection](" + root_url + ") or the "
        "[original Critical Systems series]"
        "(https://mateopetel.substack.com/t/forward-science). "
        "These are two editions of the author's work, "
        "not independent confirmations of the arguments.",
        "",
        "## Concepts",
        "",
        "- **Forward Science:** institutional practices that connect new technical "
        "capability with scientific evidence and action. "
        f"Read [Forward Science]({root_url}forward-science/).",
        "- **Forward-deployed scientist / deployed scientist:** the embedded "
        "scientist-builder role developed in the series. "
        f"Read [Forward-Deployed Scientists]({root_url}forward-deployed-scientists/).",
        "- **Scientific loop:** the cycle connecting questions, experiments, "
        "evidence, judgment, and the next scientific action. "
        f"Read [The Unit of Deployment Is the Scientific Loop]({root_url}scientific-loop/).",
        "",
        "## Essays and original publications",
        "",
    ]
    for number, essay in enumerate(essays, start=1):
        guide.extend([
            f"### {number}. {essay['title']}",
            "",
            f"- Essay: {root_url}{essay['slug']}/",
            f"- Original publication: {essay['original_url']}",
            f"- Publication date: {essay['date']}",
            f"- Summary: {essay['summary']}",
            f"- Subjects: {', '.join(TOPICS[essay['slug']])}",
            "",
        ])
    guide.extend([
        "## Source and attribution",
        "",
        "Author: Mateo H. Petel. The linked HTML articles reproduce the "
        "imported essay texts, with source references retained. "
        "Consult the original Substack links for the initial publications. "
        "The website's import checksums establish correspondence with its "
        "stored source export, not independent verification of scientific claims.",
        "",
    ])
    (output / "llms.txt").write_text("\n".join(guide), encoding="utf-8")

    provenance = json.loads(
        (root / "content" / "import-provenance.json").read_text(encoding="utf-8")
    )
    published = {r["slug"]: r["source_date_raw"] for r in provenance}
    if set(published) != {e["slug"] for e in essays}:
        raise ValueError("Feed provenance must match the essay manifest")
    for essay in essays:
        value = published[essay["slug"]]
        if not isinstance(value, str) or not value.startswith(essay["date"] + "T"):
            raise ValueError(f"Invalid source publication timestamp: {essay['slug']}")

    namespace = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", namespace)

    def add(parent: ET.Element, tag: str, value: str | None = None,
            **attributes: str) -> ET.Element:
        child = ET.SubElement(parent, f"{{{namespace}}}{tag}", attributes)
        child.text = value
        return child

    feed = ET.Element(f"{{{namespace}}}feed")
    add(feed, "id", root_url)
    add(feed, "title", "Forward Science")
    add(feed, "subtitle", "Six essays on institutions for AI-enabled science")
    add(feed, "updated", max(published.values()))
    add(feed, "link", rel="self", href=root_url + "feed.xml",
        type="application/atom+xml")
    add(feed, "link", rel="alternate", href=root_url, type="text/html")
    add(add(feed, "author"), "name", "Mateo H. Petel")
    for essay in sorted(essays, key=lambda e: published[e["slug"]], reverse=True):
        article_url = f"{root_url}{essay['slug']}/"
        entry = add(feed, "entry")
        add(entry, "id", article_url)
        add(entry, "title", essay["title"])
        add(entry, "published", published[essay["slug"]])
        add(entry, "updated", published[essay["slug"]])
        add(entry, "summary", essay["summary"])
        add(entry, "link", rel="alternate", href=article_url, type="text/html")
        add(entry, "link", rel="related", href=essay["original_url"],
            type="text/html")
    (output / "feed.xml").write_bytes(
        ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    )
