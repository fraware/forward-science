#!/usr/bin/env python3
"""Build the dependency-free, static Forward Science publication.

Dependencies are needed only during building. The generated site consists of
ordinary HTML, CSS, a favicon, and optional sitemap files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SUBSTACK_SUBSCRIBE_FOOTER = (
    '<p><a href="https://mateopetel.substack.com/subscribe?" '
    'rel="noopener noreferrer"><span>Subscribe now</span></a></p>'
)


class TextOnly(HTMLParser):
    """Count meaningful text in imported sanitized HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def verify_base_url(raw: str | None) -> str | None:
    """Accept only HTTPS origins, optionally with a GitHub Pages path prefix."""
    if not raw:
        return None
    u = urlsplit(raw.rstrip("/"))
    if u.scheme != "https" or not u.netloc or u.query or u.fragment or u.username or u.password:
        raise ValueError("--base-url must be an HTTPS URL without query or fragment")
    if ".." in u.path.split("/"):
        raise ValueError("--base-url must not contain parent directory segments")
    return raw.rstrip("/")


def load_essays(root: Path) -> list[dict]:
    """Validate the fixed corpus and load any verified imported bodies."""
    manifest = json.loads((root / "content" / "essays.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or len(manifest) != 6:
        raise ValueError("Forward Science must have exactly six records")
    slugs: set[str] = set()
    landmark_map = json.loads((root / "content" / "landmarks.json").read_text(encoding="utf-8"))
    if set(landmark_map) != {record["slug"] for record in manifest}:
        raise ValueError("Navigation landmarks must cover precisely the six essays")
    audio_manifest = json.loads((root / "content" / "audio.json").read_text(encoding="utf-8"))
    if not isinstance(audio_manifest, dict) or set(audio_manifest) - set(landmark_map):
        raise ValueError("Audio manifest contains unrecognized essays")
    for position, e in enumerate(manifest):
        e["chapter_roman"] = ("I", "II", "III", "IV", "V", "VI")[position]
        if e["number"] != f"{position:02d}" or not SLUG.fullmatch(e["slug"]):
            raise ValueError(f"Invalid sequence/slug: {e}")
        if e["slug"] in slugs:
            raise ValueError(f"Duplicate slug: {e['slug']}")
        slugs.add(e["slug"])
        if not e["original_url"].startswith("https://mateopetel.substack.com/p/"):
            raise ValueError(f"Unexpected source URL for {e['slug']}")
        published = date.fromisoformat(e["date"])
        e["date_long"] = f"{published:%B} {published.day}, {published.year}"
        body_path = root / "content" / "essays" / f"{e['slug']}.html"
        e["complete"] = body_path.is_file()
        e["body"] = body_path.read_text(encoding="utf-8") if e["complete"] else ""
        # Keep the imported source intact for checksum verification. The final
        # Substack subscription widget is distribution boilerplate, not essay prose.
        e["display_body"] = e["body"].strip().removesuffix(SUBSTACK_SUBSCRIBE_FOOTER).strip()
        # Anchors are added only to rendered HTML; source and provenance stay immutable.
        paragraphs = 0
        def number_paragraph(match: re.Match[str]) -> str:
            nonlocal paragraphs
            paragraphs += 1
            return f'<p id="p-{paragraphs:02d}">'
        e["display_body"] = re.sub(r"<p>", number_paragraph, e["display_body"])
        e["paragraph_count"] = paragraphs
        positions = landmark_map[e["slug"]]
        if not isinstance(positions, list) or not (3 <= len(positions) <= 7):
            raise ValueError(f"Invalid navigation landmark count: {e['slug']}")
        previous_position = -1
        e["landmarks"] = []
        for index, label in positions:
            if (not isinstance(index, int) or index <= previous_position
                    or not isinstance(label, str) or not label.strip() or len(label) > 90
                    or (e["complete"] and index >= paragraphs)):
                raise ValueError(f"Invalid landmark: {e['slug']} at {index}")
            if e["complete"]:
                e["landmarks"].append({"label": label, "anchor": f"p-{index+1:02d}"})
            previous_position = index
        e["audio"] = None
        e["audio_sha256"] = None
        e["audio_voice"] = None
        e["audio_preview"] = False
        e["audio_source"] = None
        recording = audio_manifest.get(e["slug"])
        if recording is not None:
            if not isinstance(recording, dict) or recording.get("path") != f"media/{e['slug']}.mp3":
                raise ValueError(f"Invalid audio path: {e['slug']}")
            source_file = root / recording["path"]
            if not source_file.is_file():
                raise ValueError(f"Audio file missing: {e['slug']}")
            actual_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
            if actual_sha != recording.get("sha256"):
                raise ValueError(f"Audio checksum mismatch: {e['slug']}")
            e["audio"] = recording["path"]
            e["audio_source"] = source_file
            e["audio_sha256"] = actual_sha
            voice = recording.get("voice")
            if isinstance(voice, dict):
                # Strict publication validates attribution and rights separately.
                e["audio_voice"] = {
                    "type": voice.get("type"),
                    "name": voice.get("name"),
                    "provider": voice.get("provider"),
                }
        if e["complete"]:
            if not e["body"].strip():
                raise ValueError(f"Empty body file: {body_path}")
            parser = TextOnly()
            parser.feed(e["body"])
            word_count = len(" ".join(parser.text).split())
            if word_count < 300:
                raise ValueError(f"Imported full essay suspiciously short: {e['slug']} ({word_count} words)")
    return manifest



def validate_provenance(root: Path, essays: list[dict]) -> None:
    """Fail closed if validated imports have been altered since extraction.

    This verifies internal consistency, not independent correspondence with
    the latest Substack web edition; a human comparison remains necessary.
    """
    report = root / "content" / "import-provenance.json"
    if not report.is_file():
        raise ValueError("Missing import-provenance.json; run the official author-export importer")
    records = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != len(essays):
        raise ValueError("Invalid import provenance record count")
    if [r.get("slug") for r in records] != [e["slug"] for e in essays]:
        raise ValueError("Import provenance order or identity differs from the essay manifest")
    for e, record in zip(essays, records, strict=True):
        content_hash = hashlib.sha256(e["body"].strip().encode("utf-8")).hexdigest()
        if content_hash != record.get("rendered_sha256"):
            raise ValueError(f"Imported article modified since verification: {e['slug']}")
        if record.get("original_url") != e["original_url"]:
            raise ValueError(f"Imported article has a mismatched original URL: {e['slug']}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("source_sha256", ""))):
            raise ValueError(f"Missing raw source SHA-256: {e['slug']}")
        if int(record.get("source_word_count", 0)) < 300:
            raise ValueError(f"Invalid source word count: {e['slug']}")


def build(root: Path, output: Path, base_url: str | None,
          strict: bool = False, preview_dir: Path | None = None) -> list[dict]:
    """Render the site; strict mode prevents deploying preview-only chapters."""
    base_url = verify_base_url(base_url)
    # Never allow a generated-output path to overlap source or repository
    # authority: a caller-supplied --out must not destroy editable files.
    source_root = root.resolve()
    # Only the designated site/ directory is writable inside the repository.
    # All other outputs must be outside the repository tree, including docs/,
    # tests/, browser/, .git/, and nested destinations under site/.
    if output.is_symlink():
        raise ValueError("Generated output path is a symlink")
    target_root = output.resolve()
    publication_root = source_root / "site"
    if (target_root == source_root or source_root.is_relative_to(target_root)
            or (target_root.is_relative_to(source_root)
                and target_root != publication_root)):
        raise ValueError("Generated output overlaps publication sources or repository files")
    # Reject existing symlinks before generating any files. The later strict
    # allowlist still protects the final upload, but checks after writes alone
    # would allow a preexisting symlinked chapter directory to be overwritten.
    if output.is_dir():
        for existing in output.rglob("*"):
            if existing.is_symlink():
                if existing == output / "media":
                    raise ValueError("Output media path is a symlink")
                raise ValueError(f"Symlink forbidden in generated publication: {existing}")
    essays = load_essays(root)
    if preview_dir is not None:
        if preview_dir.resolve().is_relative_to(output.resolve()):
            raise ValueError("Private preview source cannot be inside generated public output")
        # Preview publication has its own pinned, source-and-byte verification.
        # It is never a substitute for final signed listening acceptance.
        import importlib.util
        script = Path(__file__).with_name("verify_audio_previews.py")
        spec = importlib.util.spec_from_file_location("forward_science_preview_gate", script)
        if spec is None or spec.loader is None:
            raise ValueError("Missing preview media verifier")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        preview = module.validate(root, preview_dir)
        for essay in essays:
            if essay["audio"] is not None:
                raise ValueError("A reviewed edition cannot be overwritten by a preview")
            record = preview[essay["slug"]]
            essay["audio"] = record["path"]
            essay["audio_source"] = record["file"]
            essay["audio_sha256"] = record["sha256"]
            essay["audio_voice"] = record["voice"]
            essay["audio_preview"] = True
    incomplete = [e["slug"] for e in essays if not e["complete"]]
    if strict and incomplete:
        raise ValueError("Refusing to publish incomplete chapters: " + ", ".join(incomplete))
    if strict:
        validate_provenance(root, essays)
        if any(essay["audio"] and not essay["audio_preview"] for essay in essays):
            # Release authorization is separate from file-hash verification:
            # validate manuscript, accountable listening review and MP3 decoding.
            import importlib.util
            script = Path(__file__).with_name("verify_audio.py")
            spec = importlib.util.spec_from_file_location("forward_science_audio_gate", script)
            if spec is None or spec.loader is None:
                raise ValueError("Missing MP3 release verifier")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.validate(root)
    env = Environment(
        loader=FileSystemLoader(str(root / "templates")),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    output.mkdir(parents=True, exist_ok=True)
    # A revoked audio manifest must withdraw previously generated media even
    # on an incremental local build. Symlinks fail closed instead of allowing
    # a build to affect files outside the output directory.
    previous_media = output / "media"
    if previous_media.is_symlink():
        raise ValueError("Output media path is a symlink")
    if previous_media.is_dir():
        shutil.rmtree(previous_media)
    elif previous_media.exists():
        raise ValueError("Output media path is not a directory")
    # Clean legacy public downloads from earlier builds. Author-only exports
    # remain available through scripts/export_editions.py, never through Pages.
    obsolete_downloads = output / "downloads"
    if obsolete_downloads.is_dir():
        shutil.rmtree(obsolete_downloads)
    # Retract the former system-voice JavaScript when rebuilding an old site.
    (output / "device-narration.js").unlink(missing_ok=True)
    (output / "index.html").write_text(
        env.get_template("index.html.j2").render(essays=essays, base_url=base_url), encoding="utf-8"
    )
    for i, essay in enumerate(essays):
        page = output / essay["slug"]
        page.mkdir(parents=True, exist_ok=True)
        html = env.get_template("essay.html.j2").render(
            essay=essay,
            essays=essays,
            previous=essays[i - 1] if i else None,
            next=essays[i + 1] if i + 1 < len(essays) else None,
            base_url=base_url,
        )
        (page / "index.html").write_text(html, encoding="utf-8")
    for filename in ("styles.css", "favicon.svg", "reader.js"):
        shutil.copy2(root / filename, output / filename)
    for essay in essays:
        if essay["audio"]:
            target = output / essay["audio"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(essay["audio_source"], target)
    (output / ".nojekyll").touch()
    if base_url and not incomplete:
        from xml.sax.saxutils import escape
        urls = [base_url + "/"] + [base_url + "/" + e["slug"] + "/" for e in essays]
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        xml += "".join(f"  <url><loc>{escape(u)}</loc></url>\n" for u in urls)
        xml += "</urlset>\n"
        (output / "sitemap.xml").write_text(xml, encoding="utf-8")
        (output / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + base_url + "/sitemap.xml\n", encoding="utf-8")
    else:
        for filename in ("sitemap.xml", "robots.txt"):
            (output / filename).unlink(missing_ok=True)
    if strict:
        # Only explicitly generated files belong in the public artifact.
        # Catch stray private exports or stale assets before Pages uploads it.
        allowed = {
            "index.html", "styles.css", "favicon.svg", "reader.js",
            ".nojekyll", "sitemap.xml", "robots.txt",
        }
        allowed.update(f"{essay['slug']}/index.html" for essay in essays)
        allowed.update(essay["audio"] for essay in essays if essay["audio"])
        for item in output.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Symlink forbidden in generated publication: {item}")
            if item.is_file() and item.relative_to(output).as_posix() not in allowed:
                raise ValueError(f"Unexpected file in public publication: {item}")
    return essays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "site", help="Generated site directory")
    parser.add_argument("--base-url", help="Canonical website base URL, including optional GitHub Pages prefix")
    parser.add_argument("--strict", action="store_true", help="Fail unless all six full texts have been imported")
    parser.add_argument("--preview-dir", type=Path,
                        help="Six pinned, unreviewed Michael MP3s for clearly labeled website previews")
    args = parser.parse_args()
    try:
        essays = build(ROOT, args.out, args.base_url, args.strict, args.preview_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Build failed: {exc}\n")
    count = sum(e["complete"] for e in essays)
    print(f"Generated {len(essays) + 1} pages in {args.out}; complete chapters: {count}/6")
    if count < 6:
        print("Reader placeholders are marked noindex. Import the official author export before public release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
