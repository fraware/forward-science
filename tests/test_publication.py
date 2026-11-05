"""Public deployment verification checks exact bytes and removed routes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_publication", ROOT / "scripts" / "check_publication.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "scientific-loop").mkdir(parents=True)
    (site / "index.html").write_text("<h1>Forward Science</h1>", encoding="utf-8")
    (site / "scientific-loop" / "index.html").write_text("<article>Essay text</article>", encoding="utf-8")
    (site / "reader.js").write_text("void 0;", encoding="utf-8")
    (site / ".nojekyll").touch()
    return site


def mock_transport(site: Path, *, corrupt: str = "", missing: str = ""):
    def transport(url: str, method: str):
        relative = url.split("https://example.org/forward-science/", 1)[1]
        if relative.startswith("downloads/"):
            return 404, b"", {}
        if relative == missing:
            return 404, b"", {}
        if relative == "" or relative.endswith("/"):
            relative += "index.html"
        path = site / relative
        payload = path.read_bytes()
        if relative == corrupt:
            payload += b"altered"
        return 200, payload if method == "GET" else b"", {"Content-Length": str(len(payload))}
    return transport


def test_exact_public_release_matches(tmp_path: Path):
    site = fixture_site(tmp_path)
    assert module.check_once(site, "https://example.org/forward-science", mock_transport(site)) == []


def test_public_tampering_and_missing_routes_fail(tmp_path: Path):
    site = fixture_site(tmp_path)
    corrupt = module.check_once(site, "https://example.org/forward-science", mock_transport(site, corrupt="reader.js"))
    assert any("reader.js: delivered bytes differ" in x for x in corrupt)
    missing = module.check_once(site, "https://example.org/forward-science", mock_transport(site, missing="scientific-loop/"))
    assert any("scientific-loop/: HTTP 404" in x for x in missing)


def test_rejects_remaining_public_downloads(tmp_path: Path):
    site = fixture_site(tmp_path)
    def transport(url, method):
        if "/downloads/" in url:
            return 200, b"old exported edition", {}
        return mock_transport(site)(url, method)
    errors = module.check_once(site, "https://example.org/forward-science", transport)
    assert len([x for x in errors if "removed public edition" in x]) == 3


def test_bad_origins_rejected():
    for url in ("http://example.org", "https://example.org/../other",
                "https://user:pass@example.org", "https://example.org/?a=1"):
        with pytest.raises(ValueError):
            module.valid_origin(url)


def test_large_files_use_head_only(tmp_path: Path, monkeypatch):
    site = fixture_site(tmp_path)
    monkeypatch.setattr(module, "LARGE_FILE_BYTES", 4)
    seen = []
    delegate = mock_transport(site)
    def transport(url, method):
        seen.append((url, method))
        return delegate(url, method)
    assert module.check_once(site, "https://example.org/forward-science", transport) == []
    assert any(url.endswith("/reader.js") and method == "HEAD" for url, method in seen)
