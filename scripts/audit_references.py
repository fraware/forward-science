#!/usr/bin/env python3
"""Create a source-faithful, offline reference inventory for six Forward Science essays.

Citation presence is a structural property; source relevance and evidentiary
sufficiency must be assessed by an editor. This program never fetches links,
changes source HTML, or implies that a URL validates an adjacent assertion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
COUNT = 6


def compact(value: str) -> str:
    """Normalize whitespace without changing case or substantive wording."""
    return re.sub(r"\s+", " ", value).strip()


def classify_link(url: str) -> tuple[str, str]:
    """Return kind and hostname; reject unsafe or malformed link destinations."""
    if url.startswith("#") and len(url) > 1:
        return "internal_fragment", ""
    parsed = urlsplit(url)
    if (parsed.scheme == "https" and parsed.hostname
            and not parsed.username and not parsed.password
            and not any(segment in (".", "..") for segment in parsed.path.split("/"))):
        return "external", parsed.hostname.lower()
    raise ValueError(f"Unrecognized or unsafe reference URL: {url}")


def is_export_subscription(anchor, host: str) -> bool:
    """Recognize distribution boilerplate, distinct from an essay citation."""
    parsed = urlsplit(anchor.get("href", ""))
    return (compact(anchor.get_text(" ", strip=True)) == "Subscribe now"
            and host == "mateopetel.substack.com"
            and parsed.path == "/subscribe")


def scan_html(slug: str, content: str) -> tuple[list[dict], list[dict]]:
    """Inventory every HTML hyperlink with the paragraph number used by reader."""
    soup = BeautifulSoup(content, "html.parser")
    paragraph_indices = {id(p): i for i, p in enumerate(soup.find_all("p"), start=1)}
    entries: list[dict] = []
    excluded: list[dict] = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if not isinstance(href, str):
            raise ValueError(f"{slug}: anchor missing href")
        kind, host = classify_link(href)
        label = compact(link.get_text(" ", strip=True))
        if not label:
            raise ValueError(f"{slug}: empty hyperlink label for {href}")
        paragraph = link.find_parent("p")
        paragraph_index = paragraph_indices.get(id(paragraph)) if paragraph else None
        parent_text = compact(paragraph.get_text(" ", strip=True)) if paragraph else ""
        entry = {
            "slug": slug, "paragraph": paragraph_index,
            "label": label, "url": href,
            "host": host, "kind": kind,
            "context": parent_text[:320],
        }
        if is_export_subscription(link, host):
            if paragraph is None or paragraph_index != len(paragraph_indices):
                raise ValueError(f"{slug}: subscription footer is not the final paragraph")
            excluded.append(entry)
        else:
            entries.append(entry)
    return entries, excluded


def build_inventory(root: Path) -> dict:
    """Check immutable source hashes and enumerate every original citation."""
    essays = json.loads((root / "content" / "essays.json").read_text(encoding="utf-8"))
    provenance = json.loads((root / "content" / "import-provenance.json").read_text(encoding="utf-8"))
    if not isinstance(essays, list) or len(essays) != COUNT:
        raise ValueError("Expected exactly six essays")
    if not isinstance(provenance, list) or len(provenance) != COUNT:
        raise ValueError("Expected exactly six original import records")
    if [x["slug"] for x in essays] != [x["slug"] for x in provenance]:
        raise ValueError("Source and provenance order/identity differ")

    citations: list[dict] = []
    excluded: list[dict] = []
    for essay, record in zip(essays, provenance, strict=True):
        slug = essay["slug"]
        path = root / "content" / "essays" / f"{slug}.html"
        content = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
        if digest != record["rendered_sha256"]:
            raise ValueError(f"{slug}: imported source differs from recorded SHA-256")
        entries, boilerplate = scan_html(slug, content)
        citations.extend(entries)
        excluded.extend(boilerplate)

    per_essay = {e["slug"]: sum(c["slug"] == e["slug"] for c in citations) for e in essays}
    external = [c for c in citations if c["kind"] == "external"]
    unique = sorted(set(c["url"] for c in external))
    return {
        "schema_version": 1,
        "scope": "exact source-verified author-export HTML; no network verification",
        "essays": per_essay,
        "citation_count": len(citations),
        "distinct_external_urls": len(unique),
        "excluded_subscription_footers": len(excluded),
        "citations": citations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Optional JSON evidence file outside the publication")
    args = parser.parse_args()
    try:
        report = build_inventory(ROOT)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REFERENCE INVENTORY INVALID: {exc}", file=sys.stderr)
        return 1
    print("Source-verified reference inventory:")
    for slug, count in report["essays"].items():
        print(f"  {slug}: {count} substantive citations")
    print(f"  Total: {report['citation_count']} references, "
          f"{report['distinct_external_urls']} distinct external URLs; "
          f"{report['excluded_subscription_footers']} export subscription footers excluded")
    print("Structural inventory only. Human evidence/claim review remains necessary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
