#!/usr/bin/env python3
"""Compare six author-export essays with Substack's current public post bodies.

This check is read-only. It never refreshes or rewrites the source edition.
The single-post JSON endpoint is undocumented and can be inaccessible or change
shape; that outcome is reported as unavailable, never as a successful match.

Usage:
    python scripts/audit_live_substack.py
    python scripts/audit_live_substack.py --json /tmp/live-audit.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_HOST = "mateopetel.substack.com"
MAX_RESPONSE_BYTES = 2_000_000
MAX_POSTS = 6
MAX_TEXT_PREVIEW = 110
SPACE = re.compile(r"\s+")


class UnavailableSource(Exception):
    """Current public source could not be reliably obtained or interpreted."""


def normalize_text(value: str) -> str:
    """Normalize Unicode composition and whitespace, preserving punctuation/case."""
    return SPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def post_api_url(public_url: str) -> str:
    """Resolve a known public Substack post without accepting arbitrary hosts."""
    parsed = urlsplit(public_url)
    if (parsed.scheme != "https" or parsed.netloc != PUBLICATION_HOST
            or parsed.query or parsed.fragment):
        raise ValueError(f"Unrecognized publication URL: {public_url}")
    match = re.fullmatch(r"/p/([a-z0-9]+(?:-[a-z0-9]+)*)/?", parsed.path)
    if not match:
        raise ValueError(f"Unrecognized post slug: {public_url}")
    return f"https://{PUBLICATION_HOST}/api/v1/posts/{quote(match.group(1))}"


def fetch_public_post(api_url: str) -> dict:
    """Read at most 2 MB of uncredentialed, publicly accessible JSON."""
    request = Request(api_url, headers={
        "Accept": "application/json",
        "User-Agent": "ForwardScience-EditionAudit/1.0 (read-only; author-publication verification)",
    })
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise UnavailableSource(f"HTTP {response.status}")
            if urlsplit(response.geturl()).hostname != PUBLICATION_HOST:
                raise UnavailableSource("Unexpected public API redirect")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise UnavailableSource(f"Public API fetch failed: {type(exc).__name__}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise UnavailableSource("Public JSON response exceeds bounded size")
    try:
        record = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise UnavailableSource("Public response is not valid UTF-8 JSON") from exc
    if not isinstance(record, dict):
        raise UnavailableSource("Public post record has unexpected shape")
    return record


def article_evidence(body_html: str) -> tuple[list[str], list[tuple[str, str]], str, list[tuple[str, str, str]]]:
    """Extract ordered text blocks, citations, full text and media descriptors.

    Excludes the Substack subscription widget only if it is a standalone final
    paragraph. Comparing full text prevents a heading or unstructured addition
    outside a paragraph from silently evading the audit.
    """
    if not isinstance(body_html, str) or not body_html.strip():
        raise UnavailableSource("Missing public body_html")
    if len(body_html.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise UnavailableSource("Article body exceeds bounded size")
    soup = BeautifulSoup(body_html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()

    # The local author-export contains a standalone Substack subscription CTA.
    # It is distribution boilerplate and is deliberately excluded in rendering.
    paragraphs = soup.find_all("p")
    if paragraphs:
        last = paragraphs[-1]
        anchors = last.find_all("a", href=True)
        if (normalize_text(last.get_text(" ", strip=True)) == "Subscribe now"
                and len(anchors) == 1
                and urlsplit(anchors[0]["href"]).hostname == PUBLICATION_HOST
                and urlsplit(anchors[0]["href"]).path == "/subscribe"):
            last.decompose()

    block_tags = ("p", "h1", "h2", "h3", "h4", "li", "blockquote", "pre", "figcaption")
    paragraphs = [normalize_text(p.get_text(" ", strip=True)) for p in soup.find_all(block_tags)
                  if p.find(block_tags) is None]
    paragraphs = [p for p in paragraphs if p]
    links = [(normalize_text(a.get_text(" ", strip=True)), a["href"])
             for a in soup.find_all("a", href=True)]
    full_text = normalize_text(soup.get_text(" ", strip=True))
    media = [(tag.name, tag.get("src", ""), tag.get("alt", ""))
             for tag in soup.find_all(["img", "audio", "video", "iframe", "source"])]
    return paragraphs, links, full_text, media


def fingerprint(paragraphs: list[str]) -> str:
    """Hash semantic paragraph boundaries and text independently of HTML tags."""
    return hashlib.sha256("\n".join(paragraphs).encode("utf-8")).hexdigest()


def first_difference(original: list[str], live: list[str]) -> dict | None:
    """Report the earliest changed paragraph with bounded diagnostic excerpts."""
    for i in range(max(len(original), len(live))):
        before = original[i] if i < len(original) else ""
        after = live[i] if i < len(live) else ""
        if before != after:
            return {
                "paragraph": i + 1,
                "export_excerpt": before[:MAX_TEXT_PREVIEW],
                "live_excerpt": after[:MAX_TEXT_PREVIEW],
            }
    return None


def audit_one(essay: dict, provenance: dict, root: Path,
              fetch: Callable[[str], dict] = fetch_public_post) -> dict:
    """Audit a single edition, never conflating source unavailability and drift."""
    slug = essay["slug"]
    result = {"slug": slug, "url": essay["original_url"], "status": "unavailable"}
    source = root / "content" / "essays" / f"{slug}.html"
    if not source.is_file():
        result["reason"] = "Missing local original essay HTML"
        return result

    try:
        local_paragraphs, local_links, local_full_text, local_media = article_evidence(
            source.read_text(encoding="utf-8"))
        api_url = post_api_url(essay["original_url"])
        live = fetch(api_url)
        raw_body = live.get("body_html")
        if not isinstance(raw_body, str) or len(raw_body) < 300:
            raise UnavailableSource("No complete public body_html supplied")
        live_paragraphs, live_links, live_full_text, live_media = article_evidence(raw_body)
        if len(local_paragraphs) < 5 or len(live_paragraphs) < 5:
            raise UnavailableSource("Too few paragraphs for a complete-publication comparison")
        expected_id = str(provenance["source_post_id"]).split(".", 1)[0]
        observed_id = live.get("id")
        if observed_id is None or str(observed_id) != expected_id:
            raise UnavailableSource("Public post ID missing or differs from source provenance")
        if normalize_text(str(live.get("title", ""))) != normalize_text(essay["title"]):
            result.update(status="drift", reason="Public title differs from original manifest")
            return result
        if normalize_text(str(live.get("subtitle", ""))) != normalize_text(essay["subtitle"]):
            result.update(status="drift", reason="Public subtitle differs from original manifest")
            return result
        date_text = str(live.get("post_date", ""))
        if not date_text.startswith(essay["date"]):
            raise UnavailableSource("Unexpected/missing public publication date")

        result["export_paragraphs"] = len(local_paragraphs)
        result["live_paragraphs"] = len(live_paragraphs)
        result["export_fingerprint"] = fingerprint(local_paragraphs)
        result["live_fingerprint"] = fingerprint(live_paragraphs)
        diff = first_difference(local_paragraphs, live_paragraphs)
        if diff:
            result.update(status="drift", reason="Article paragraph content differs", first_difference=diff)
        elif local_full_text != live_full_text:
            result.update(status="drift", reason="Full article text differs outside matched text blocks")
        elif local_media != live_media:
            result.update(status="drift", reason="Article media differs",
                          export_media_count=len(local_media), live_media_count=len(live_media))
        elif local_links != live_links:
            difference = next((i + 1 for i in range(max(len(local_links), len(live_links)))
                               if (local_links[i] if i < len(local_links) else None)
                               != (live_links[i] if i < len(live_links) else None)), 1)
            result.update(status="drift", reason="Article citation hyperlinks differ",
                          first_link_difference=difference,
                          export_link_count=len(local_links), live_link_count=len(live_links))
        else:
            result.update(status="match", reason="Post identity, metadata, article text, media and citation hyperlinks agree")
    except (UnavailableSource, ValueError, UnicodeError, OSError) as exc:
        result.update(status="unavailable", reason=str(exc))
    return result


def audit_all(root: Path = ROOT,
              fetch: Callable[[str], dict] = fetch_public_post) -> list[dict]:
    """Require a complete, one-to-one six-essay inventory."""
    manifest = json.loads((root / "content" / "essays.json").read_text(encoding="utf-8"))
    provenance = json.loads((root / "content" / "import-provenance.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or len(manifest) != MAX_POSTS:
        raise ValueError("Expected exactly six manifest essays")
    if not isinstance(provenance, list) or len(provenance) != MAX_POSTS:
        raise ValueError("Expected exactly six provenance records")
    by_slug = {e["slug"]: e for e in provenance}
    if (len(by_slug) != MAX_POSTS or set(by_slug) != {e["slug"] for e in manifest}
            or len({e["slug"] for e in manifest}) != MAX_POSTS):
        raise ValueError("Provenance and manifest must cover the same six distinct essays")
    return [audit_one(e, by_slug[e["slug"]], root, fetch) for e in manifest]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None,
                        help="Optional path for machine-readable comparison results")
    args = parser.parse_args()
    try:
        outcomes = audit_all()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Source audit configuration failed: {exc}\n")
    report = {"edition": "author-export vs current public Substack",
              "status": "match" if all(x["status"] == "match" for x in outcomes)
              else "incomplete", "essays": outcomes}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in outcomes:
        print(f"{item['slug']}: {item['status']} — {item['reason']}")
        if "first_difference" in item:
            print(f"  earliest changed paragraph: {item['first_difference']['paragraph']}")
    if all(x["status"] == "match" for x in outcomes):
        print("LIVE EDITIONS MATCH: six complete public source editions verified")
        return 0
    if any(x["status"] == "unavailable" for x in outcomes):
        print("AUDIT INCOMPLETE: at least one public source could not be verified", file=sys.stderr)
        return 2
    print("SOURCE DRIFT: live publication differs from author export", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
