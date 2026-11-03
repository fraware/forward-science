#!/usr/bin/env python3
"""Extract exactly six Forward Science essay bodies from an author Substack export.

The importer reads only posts.csv and matching post HTML fragments from a ZIP,
never email lists or analytics. It inspects the original source, sanitizes markup,
checks text preservation, and refuses ambiguous or incomplete matches.

Usage:
    python scripts/import_substack.py ~/Downloads/substack-export.zip
    python scripts/import_substack.py ~/Downloads/substack-export.zip --apply
    python scripts/build.py --strict
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import bleach
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
MAX_POST_BYTES = 5_000_000
MAX_CSV_BYTES = 15_000_000
ALLOW_TAGS = [
    "p", "a", "strong", "b", "em", "i", "u", "h2", "h3", "h4", "ul", "ol", "li", "blockquote",
    "pre", "code", "br", "hr", "sup", "sub", "del", "s", "span", "div", "figure", "figcaption",
    "img", "table", "thead", "tbody", "tr", "th", "td", "details", "summary",
]
ALLOW_ATTRS = {
    "a": ["href", "title", "id", "name"],
    "img": ["src", "alt", "title", "width", "height"],
    "p": ["id"], "h2": ["id"], "h3": ["id"], "h4": ["id"],
    "span": ["id"], "div": ["id"], "sup": ["id"], "li": ["id"],
    "td": ["colspan", "rowspan"], "th": ["colspan", "rowspan"],
}


def normalized(value: object) -> str:
    """Normalize a title for deterministic comparisons across export formats."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", plain.lower())


def read_zip_member(archive: zipfile.ZipFile, member: str, max_bytes: int) -> bytes:
    """Read bounded decompressed bytes from one selected ZIP entry."""
    entry = archive.getinfo(member)
    if entry.file_size > max_bytes:
        raise ValueError(f"ZIP member too large: {member}")
    with archive.open(entry) as source:
        result = source.read(max_bytes + 1)
    if len(result) > max_bytes:
        raise ValueError(f"ZIP member exceeds read limit: {member}")
    return result


def find_csv(archive: zipfile.ZipFile) -> str:
    names = [n for n in archive.namelist() if n.lower().endswith("/posts.csv") or n.lower() == "posts.csv"]
    if len(names) != 1:
        raise ValueError("Expected exactly one posts.csv in the Substack archive")
    return names[0]


def load_rows(archive: zipfile.ZipFile) -> list[dict[str, str]]:
    """Read article metadata only; subscriber data is ignored."""
    member = find_csv(archive)
    raw = read_zip_member(archive, member, MAX_CSV_BYTES).decode("utf-8-sig")
    return [{str(k).strip(): str(v or "") for k, v in row.items() if k is not None}
            for row in csv.DictReader(io.StringIO(raw))]


def match_row(rows: list[dict[str, str]], title: str) -> dict[str, str]:
    """Demand a unique exact-title match to avoid publishing the wrong article."""
    exact = [r for r in rows if normalized(r.get("title", "")) == normalized(title)]
    if len(exact) != 1:
        raise ValueError(f"Expected exactly one source row for '{title}', found {len(exact)}")
    row = exact[0]
    if row.get("is_published", "").strip().lower() in {"false", "0", "no"}:
        raise ValueError(f"Unpublished source row: {title}")
    return row


def find_html(archive: zipfile.ZipFile, row: dict[str, str]) -> str:
    """Identify the corresponding HTML fragment by its source post ID."""
    source_id = str(row.get("post_id") or row.get("id") or row.get("postId") or "").strip()
    # Substack currently exports post_id as "123456789.post-slug", whereas
    # older exports and synthetic fixtures use the bare numeric identifier.
    # Match the immutable numeric prefix to the corresponding HTML filename.
    match = re.fullmatch(r"([0-9]+)(?:\.[a-zA-Z0-9_-]+)?", source_id)
    if not match:
        raise ValueError("Missing or malformed post_id in posts.csv; review export format")
    post_id = match.group(1)
    html_files = [n for n in archive.namelist()
                  if n.lower().endswith(".html") and "/posts/" in ("/" + n.lower())]
    pattern = re.compile(rf"^{re.escape(post_id)}(?:[.\-_]|\.html$)")
    matches = [n for n in html_files if pattern.match(n.rsplit("/", 1)[-1])]
    if len(matches) != 1:
        raise ValueError(f"Expected one HTML fragment for post_id {post_id}, found {len(matches)}")
    return matches[0]


def source_text(html: str) -> str:
    """Normalize only whitespace when comparing source and cleaned text."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def clean_article_html(raw: str) -> tuple[str, dict]:
    """Sanitize original markup; preserve prose, paragraphs, anchors and citations.

    A conservative HTML allowlist removes executable markup. An explicit text
    comparison makes potentially destructive conversions fail closed.
    """
    soup = BeautifulSoup(raw, "html.parser")
    # Unexpected interactive markup must be audited instead of silently
    # deleting author-visible words such as a button label or form text.
    if soup.find(["form", "button", "input", "select", "textarea"]):
        raise ValueError("Unexpected interactive elements in post body; inspect export manually")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    # A Substack export normally contains a body fragment. These wrappers, when
    # present, are stripped while keeping their contents in source order.
    fragment = str(soup.body.decode_contents()) if soup.body else str(soup)
    raw_text = source_text(fragment)
    sanitized = bleach.clean(
        fragment,
        tags=ALLOW_TAGS,
        attributes=ALLOW_ATTRS,
        protocols=["https", "http", "mailto"],
        strip=True,
        strip_comments=True,
    )
    cleaned = BeautifulSoup(sanitized, "html.parser")
    for link in cleaned.find_all("a", href=True):
        if link["href"].startswith("//"):
            link["href"] = "https:" + link["href"]
        if link["href"].startswith(("https://", "http://")):
            link["rel"] = "noopener noreferrer"
    for img in cleaned.find_all("img"):
        img["loading"] = "lazy"
        img["decoding"] = "async"
        img["referrerpolicy"] = "no-referrer"
    actual_text = source_text(str(cleaned))
    if len(raw_text.split()) < 300:
        raise ValueError(f"Suspiciously short imported text: {len(raw_text.split())} words")
    if raw_text != actual_text:
        # A dropped caption or equation is a scientific-content error, not a
        # cosmetic difference. Do not write a lossy import silently.
        raise ValueError("Import changed source text. Inspect unsupported HTML before publication")
    result = str(cleaned).strip()
    return result, {
        "source_word_count": len(raw_text.split()),
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "rendered_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
    }


def run(archive_path: Path, root: Path, apply: bool) -> list[dict]:
    """Locate, verify, and optionally write six full-text HTML fragments."""
    manifest = json.loads((root / "content" / "essays.json").read_text(encoding="utf-8"))
    if len(manifest) != 6:
        raise ValueError("Unexpected essay manifest length")
    staged: list[tuple[Path, str, dict]] = []
    with zipfile.ZipFile(archive_path) as archive:
        rows = load_rows(archive)
        for essay in manifest:
            row = match_row(rows, essay["title"])
            member = find_html(archive, row)
            raw_bytes = read_zip_member(archive, member, MAX_POST_BYTES)
            raw = raw_bytes.decode("utf-8-sig")
            clean, facts = clean_article_html(raw)
            # Source dates can differ by a day across local times and UTC;
            # preserve the independently verified publication dates in manifest.
            info = {
                "slug": essay["slug"], "title": essay["title"],
                "original_url": essay["original_url"],
                "declared_date": essay["date"],
                "source_post_id": row.get("post_id") or row.get("id") or row.get("postId"),
                "source_date_raw": row.get("post_date") or row.get("published_at") or "",
                "source_html_member": member,
                **facts,
            }
            staged.append((root / "content" / "essays" / (essay["slug"] + ".html"), clean, info))
    if apply:
        for dest, clean, _ in staged:
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_suffix(dest.suffix + ".tmp")
            temp.write_text(clean + "\n", encoding="utf-8")
            temp.replace(dest)
        report_path = root / "content" / "import-provenance.json"
        report_path.write_text(json.dumps([x[2] for x in staged], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [x[2] for x in staged]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Official Substack publication export ZIP")
    parser.add_argument("--apply", action="store_true", help="Write the six validated HTML fragments (default: dry run)")
    args = parser.parse_args()
    try:
        info = run(args.export, ROOT, args.apply)
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Import failed: {exc}\n")
    for record in info:
        print(f"{record['slug']}: {record['source_word_count']} words, SHA256 {record['source_sha256'][:12]}…")
    print("Imported six articles." if args.apply else "Dry run passed. Re-run with --apply to write the verified articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
