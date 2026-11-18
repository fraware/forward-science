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


# These editorial definitions summarize the arguments in the corresponding essays.
# They are navigational descriptions, not alterations of the original text.
CONCEPTS = [
    {
        "id": "forward-science",
        "term": "Forward Science",
        "definition": "An institutional approach to incorporating AI, computation, and automation into scientific inquiry through accountable evidence, judgment, and research decisions.",
        "essay_slug": "forward-science",
        "related_terms": ["AI for science", "scientific institutions"],
    },
    {
        "id": "forward-deployed-scientist",
        "term": "Forward-Deployed Scientist",
        "definition": "A scientist-builder working within a research environment to connect advanced technical systems with the laboratory's questions, instruments, evidentiary standards, and next experiments.",
        "essay_slug": "forward-deployed-scientists",
        "related_terms": ["forward-deployed scientists", "deployed scientists"],
    },
    {
        "id": "scientific-loop",
        "term": "Scientific Loop",
        "definition": "The organized passage from a research question through representation, experimentation, measurement, interpretation, and validation to an informed subsequent action.",
        "essay_slug": "scientific-loop",
        "related_terms": ["experimental validation", "research loop"],
    },
    {
        "id": "scientific-intermediaries",
        "term": "Scientific Intermediaries",
        "definition": "People and institutional roles that translate established scientific knowledge or technical capability into situated research practice, including the traditions of extension work and research software engineering.",
        "essay_slug": "extension-agents",
        "related_terms": ["agricultural extension", "research software engineering"],
    },
    {
        "id": "scientific-capacity",
        "term": "Scientific Capacity",
        "definition": "A research institution's sustained ability to conduct and improve inquiry, considered alongside the funding, credit, governance, and careers that support deployed scientific expertise.",
        "essay_slug": "political-economy",
        "related_terms": ["research funding", "scientific workforce"],
    },
    {
        "id": "self-driving-laboratory",
        "term": "Self-Driving Laboratory",
        "definition": "A research environment that integrates automation and computational decisions across experiments; its scientific value depends on sound evidence, memory, validation, and human or institutional judgment.",
        "essay_slug": "future-laboratory",
        "related_terms": ["laboratory automation", "loop-governed laboratory"],
    },
]


def schemas(essays: list[dict], base_url: str) -> tuple[dict, dict[str, dict]]:
    """Return Schema.org collection and article graphs for published essays."""
    if set(TOPICS) != {e["slug"] for e in essays}:
        raise ValueError("Discovery subjects must match the entire essay manifest")
    root_url = base_url + "/"
    # Reuse the public author's stable entity ID across both websites.
    author_id = "https://mateopetel.xyz/#person"
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
                    "keywords": list(TOPICS[essay["slug"]]),
                    "isAccessibleForFree": True,
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


def concept_schema(essays: list[dict], base_url: str) -> dict:
    """Describe the separate concept guide without treating it as an original essay."""
    if {c["essay_slug"] for c in CONCEPTS} != {e["slug"] for e in essays}:
        raise ValueError("Concept definitions must map to the published corpus")
    root_url = base_url + "/"
    url = root_url + "concepts/"
    defined_terms = [
        {
            "@type": "DefinedTerm",
            "@id": url + "#" + concept["id"],
            "name": concept["term"],
            "description": concept["definition"],
            "url": url + "#" + concept["id"],
            "inDefinedTermSet": {"@id": url + "#terms"},
            "subjectOf": {"@id": root_url + concept["essay_slug"] + "/#article"},
        }
        for concept in CONCEPTS
    ]
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage", "@id": url + "#webpage",
                "url": url, "name": "Concepts in Forward Science",
                "description": "Definitions and primary essay references for six concepts in Forward Science.",
                "inLanguage": "en", "isPartOf": {"@id": root_url + "#website"},
                "mainEntity": {"@id": url + "#terms"},
            },
            {
                "@type": "DefinedTermSet", "@id": url + "#terms",
                "url": url, "name": "Forward Science concepts",
                "description": "An editorial guide to concepts introduced across the six essays.",
                "hasDefinedTerm": [{"@id": term["@id"]} for term in defined_terms],
            },
            *defined_terms,
        ],
    }


def corpus_index(essays: list[dict], base_url: str) -> dict:
    """Expose factual source and reading metadata for retrieval systems."""
    root_url = base_url + "/"
    return {
        "schema_version": 1,
        "title": "Forward Science",
        "url": root_url,
        "language": "en",
        "description": "Six essays on institutions for AI-enabled scientific discovery.",
        "author": {
            "name": "Mateo H. Petel",
            "website": "https://mateopetel.xyz/",
            "original_publications": "https://mateopetel.substack.com/t/forward-science",
            "github": "https://github.com/fraware",
        },
        "concept_guide": root_url + "concepts/",
        "concepts": [
            {
                **concept,
                "url": root_url + "concepts/#" + concept["id"],
                "primary_essay": root_url + concept["essay_slug"] + "/",
            }
            for concept in CONCEPTS
        ],
        "essays": [
            {
                "position": index,
                "title": essay["title"],
                "subtitle": essay["subtitle"],
                "summary": essay["summary"],
                "date_published": essay["date"],
                "url": root_url + essay["slug"] + "/",
                "original_publication": essay["original_url"],
                "subjects": list(TOPICS[essay["slug"]]),
                "navigation": [
                    {
                        "label": landmark["label"],
                        "url": root_url + essay["slug"] + "/#" + landmark["anchor"],
                    }
                    for landmark in essay["landmarks"]
                ],
            }
            for index, essay in enumerate(essays, start=1)
        ],
        "rights": "Essays and original editorial content © 2026 Mateo H. Petel. All rights reserved.",
        "source_note": "This metadata describes the author's essays; it does not independently verify their claims.",
    }


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
        "## Machine-readable navigation",
        "",
        f"- [Concept guide]({root_url}concepts/): short definitions with primary essay references.",
        f"- [Corpus metadata]({root_url}corpus.json): JSON index of essay URLs, concepts, dates, and section anchors.",
        f"- [XML sitemap]({root_url}sitemap.xml): canonical HTML routes.",
        f"- [Atom feed]({root_url}feed.xml): original publication timestamps.",
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
    (output / "corpus.json").write_text(
        json.dumps(corpus_index(essays, base_url), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
