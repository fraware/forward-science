#!/usr/bin/env python3
"""Independently compare the public GitHub Pages release with the built artifact.

Runs on a network-enabled GitHub Actions runner after deployment. Local
tests use an injected transport and never require external network access.
"""
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

OMITTED_FILES = {".nojekyll"}
REMOVED_DOWNLOADS = (
    "downloads/forward-science.pdf",
    "downloads/forward-science.epub",
    "downloads/forward-science.md",
)
LARGE_FILE_BYTES = 3_000_000


def valid_origin(value: str) -> str:
    """Accept an HTTPS Pages root, including a possible project subdirectory."""
    parsed = urlsplit(value.rstrip("/"))
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or any(segment in (".", "..") for segment in parsed.path.split("/"))):
        raise ValueError("Public base URL must be an absolute HTTPS site root")
    return value.rstrip("/")


def request_public(url: str, method: str = "GET") -> tuple[int, bytes, dict[str, str]]:
    """Retrieve one public asset without reading GitHub API credentials."""
    req = Request(
        url,
        method=method,
        headers={
            "User-Agent": "ForwardScience-PublicReleaseAudit/1.0",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, response.read() if method == "GET" else b"", dict(response.headers)
    except HTTPError as exc:
        return exc.code, b"", {}


def published_path(relative: Path) -> str:
    """Use directory URLs for index files, mirroring reader navigation."""
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "" if parent == "." else parent + "/"
    return relative.as_posix()


def check_once(
    site: Path,
    base_url: str,
    transport=request_public,
) -> list[str]:
    """Report every public mismatch without conflating a deploy with a live check."""
    origin = valid_origin(base_url)
    if not site.is_dir() or not (site / "index.html").is_file():
        raise ValueError("Expected generated site/ directory with index.html")
    problems: list[str] = []
    for asset in sorted(p for p in site.rglob("*") if p.is_file()):
        relative = asset.relative_to(site)
        if asset.name in OMITTED_FILES:
            continue
        route = published_path(relative)
        url = origin + "/" + route
        # Published narration must match the approved media checksum byte-for-byte.
        # A HEAD/Content-Length check cannot detect same-length audio substitution.
        method = ("GET" if asset.suffix.lower() == ".mp3"
                  or asset.stat().st_size <= LARGE_FILE_BYTES else "HEAD")
        try:
            status, content, headers = transport(url, method)
            if status != 200:
                problems.append(f"{route}: HTTP {status}, expected 200")
                continue
            if method == "GET":
                actual = hashlib.sha256(content).hexdigest()
                expected = hashlib.sha256(asset.read_bytes()).hexdigest()
                if actual != expected:
                    problems.append(f"{route}: delivered bytes differ from release artifact")
            else:
                length = headers.get("Content-Length") or headers.get("content-length")
                if length is not None and int(length) != asset.stat().st_size:
                    problems.append(f"{route}: delivered content length differs from release artifact")
        except (OSError, ValueError, TimeoutError) as exc:
            problems.append(f"{route}: fetch failed ({type(exc).__name__}: {exc})")

    for old in REMOVED_DOWNLOADS:
        url = origin + "/" + old
        try:
            status, _, _ = transport(url, "GET")
            if status != 404:
                problems.append(f"{old}: removed public edition returned HTTP {status}, expected 404")
        except (OSError, ValueError, TimeoutError) as exc:
            problems.append(f"{old}: unable to confirm removal ({type(exc).__name__}: {exc})")
    return problems


def check_with_retries(
    site: Path, base_url: str, attempts: int = 8, delay: float = 12.0
) -> None:
    """Retry boundedly for Pages CDN propagation; fail the workflow if unverified."""
    if not 1 <= attempts <= 20 or not 0 <= delay <= 60:
        raise ValueError("Invalid bounded retry settings")
    for attempt in range(1, attempts + 1):
        failures = check_once(site, base_url)
        if not failures:
            print(f"PUBLIC RELEASE VERIFIED: all site files and removed-download routes ({attempt=})")
            return
        print(f"Public verification attempt {attempt}/{attempts}: {len(failures)} problem(s)")
        for problem in failures[:16]:
            print(f"  - {problem}")
        if attempt != attempts:
            time.sleep(delay)
    raise RuntimeError("Public release differs from the expected Pages artifact")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--delay", type=float, default=12.0)
    args = parser.parse_args()
    check_with_retries(args.site, args.base_url, attempts=args.attempts, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
