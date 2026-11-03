#!/usr/bin/env python3
"""Create a six-essay-only ZIP from a private full Substack author export.

This utility reads the original ZIP but writes only a minimal posts.csv and six
corresponding article HTML bodies. Subscriber email lists, delivery analytics,
other articles, and unrelated private export files never enter the output.

Usage:
  python scripts/prepare_private_export.py FULL_EXPORT.zip forward-science-only.zip
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from pathlib import Path

from import_substack import ROOT, find_html, load_rows, match_row, read_zip_member, MAX_POST_BYTES

FIELDS = ("post_id", "title", "post_date", "is_published")


def select_essays(original: Path, destination: Path) -> None:
    """Validate the six exact matches and create an exclusionary export."""
    if original.resolve() == destination.resolve():
        raise ValueError("Output must differ from the original private ZIP")
    manifest = json.loads((ROOT / "content" / "essays.json").read_text(encoding="utf-8"))
    verified: list[tuple[dict, bytes]] = []
    with zipfile.ZipFile(original) as source:
        rows = load_rows(source)
        for essay in manifest:
            row = match_row(rows, essay["title"])
            member = find_html(source, row)
            body = read_zip_member(source, member, MAX_POST_BYTES)
            post_id = row.get("post_id") or row.get("id") or row.get("postId")
            verified.append(({
                "post_id": post_id,
                "title": row["title"],
                "post_date": row.get("post_date", ""),
                "is_published": row.get("is_published", "true"),
            }, body))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as target:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row for row, _ in verified)
        target.writestr("posts.csv", buffer.getvalue())
        for row, body in verified:
            target.writestr(f"posts/{row['post_id']}.html", body)
    with zipfile.ZipFile(destination) as validation:
        assert len(validation.namelist()) == 7  # one manifest + exactly six bodies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="Full private publication export ZIP")
    parser.add_argument("destination", type=Path, help="New shareable six-essay-only ZIP")
    args = parser.parse_args()
    try:
        select_essays(args.original, args.destination)
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Preparation failed: {exc}\n")
    print(f"Created {args.destination}: six post bodies + restricted posts.csv, no subscriber lists or analytics")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
