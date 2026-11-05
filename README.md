# Forward Science

A typography-first, dependency-free static website for the six Forward Science publications by Mateo H. Petel, originally published June 22–27, 2026.

**Editorial sequence:** The foundational essay (`00`), then five chapters (`01–05`). The first and second chapters explicitly identify their order in the original articles; their publication dates run in a different order. The concluding essay is absent from the Substack tag listing but was verified at its standalone publication URL.

## Current state

- Homepage and six local chapter routes are generated from one verified `content/essays.json` manifest.
- All six full-length essays have been imported from the author's official November 2026 Substack export, including the final essay missing from the Substack tag page. They are available as local reading pages.
- The original essay prose is **never paraphrased by the importer**. Permitted HTML elements are retained and active content is removed; a text-equivalence check fails closed on changed prose. The strict build checks each imported body against its recorded SHA-256 hash.
- The original export contained unrelated posts, subscriber information, and delivery analytics. None of those private files were copied into this project. Only six sanitized article bodies and their bounded provenance metadata are included.
- The importer and strict deployment workflow refuse to pass partial or ambiguous imports as complete texts. Deployment runs on pushes to `main` and by manual dispatch; continuous integration runs on pushes and pull requests.
- **Publication status:** The complete publication is committed to `fraware/forward-science`. A GitHub Pages deployment job completed successfully on November 3, 2026 (UTC). Independent HTTP inspection, live-Substack paragraph comparison, and custom-domain selection remain open.

## Project layout

```text
content/essays.json         Titles, source links, concepts and publication dates
content/essays/*.html      The six sanitized, imported original article bodies
templates/                 HTML templates, metadata, navigation
scripts/build.py           Static site compiler
scripts/import_substack.py Author-export importer with content-integrity checks
scripts/prepare_private_export.py Removes subscriber data and unrelated posts before sharing
styles.css                 Editorial design and responsive reading typography
favicon.svg                Simple lettermark
site/                      Generated output; publish this directory
.github/workflows/pages.yml Strict GitHub Pages deployment
```

## Preview locally

```bash
python -m pip install -r requirements-build.txt
python scripts/build.py
python -m http.server --directory site 8000
```

Visit `http://localhost:8000`. The site itself has no JavaScript, analytics, external fonts or runtime dependencies.

## Import the exact six essays

The six full source essays are now imported from the author's supplied official Substack export. The process is reproducible from a fresh export. Substack documents the export under **Publication dashboard → Settings → Exports → Create new export** (see https://support.substack.com/hc/en-us/articles/360037466012-How-do-I-export-my-posts).

The ZIP contains subscriber information and other unrelated material; **do not commit or share that ZIP publicly**. Upload it privately to the working environment, or run the importer locally:

```bash
python scripts/import_substack.py /path/to/substack-export.zip
python scripts/import_substack.py /path/to/substack-export.zip --apply
python scripts/build.py --strict
```

For a privacy-minimized upload, generate an archive containing only the six posts:

```bash
python scripts/prepare_private_export.py /path/to/substack-export.zip /path/to/forward-science-only.zip
```

This derivative ZIP contains only the six article bodies and the minimum post metadata necessary for the importer. Use that smaller ZIP for sharing or importing; retain the original export privately.

The first command verifies all six texts in dry-run mode. The second writes sanitized article bodies to `content/essays/` and an `import-provenance.json` report with SHA-256 fingerprints, word counts, dates and source IDs. The importer deliberately rejects ambiguous matches, missing HTML, suspiciously short bodies, unreviewed interactive markup and any loss of textual content. The source HTML fragments, which are author-owned content, can be versioned with this repository; never commit the export ZIP or its subscriber metadata.

**Editorial verification still necessary:** Compare each of the six exported bodies against the latest live publication paragraph by paragraph, review external reference destinations and any notation, and decide whether to preserve or separately edit original typographical errors. The six exported bodies contain no embedded images or iframes. Their text, titles, subtitles and publication dates are consistent with the source metadata. An import hash proves consistency with the supplied export, not identity to a subsequently edited live post.

## Deployment

- Repository: https://github.com/fraware/forward-science
- Configured site: https://fraware.github.io/forward-science/
- Publication workflow: `.github/workflows/pages.yml` runs on pushes to `main` or manual dispatch.
- The deployment job runs all tests and strict source-integrity checks before uploading the `site/` artifact.
- Canonical URLs default to `https://fraware.github.io/forward-science`. To use a verified custom domain, set the optional Actions variable `SITE_BASE_URL` to its HTTPS root and redeploy.
- The Substack “Subscribe now” export footer is omitted only during rendering. The versioned imported article bodies and SHA-256 provenance remain unchanged.

GitHub Actions reports a successful deployment. Independent HTTP inspection of the public address, a live Substack edition comparison, and final domain selection remain necessary before announcing the publication. Never commit subscriber exports or unrelated analytics.

### Search engine policy

Preview-only chapter pages are `noindex` and canonicalized to their original Substack URL. With all complete texts present and `--base-url` provided, canonical URLs and `sitemap.xml` use the permanent website. Decide on the preferred canonical versions and coordinate this with the original Substack publications.

## Test

```bash
python -m pytest -q
python scripts/build.py --strict  # now succeeds with all six imported texts
```

## Original publications

- https://mateopetel.substack.com/p/forward-science
- https://mateopetel.substack.com/p/forward-deployed-scientists
- https://mateopetel.substack.com/p/the-unit-of-deployment-is-the-scientific
- https://mateopetel.substack.com/p/from-extension-agents-to-forward
- https://mateopetel.substack.com/p/who-pays-for-the-scientist-who-makes
- https://mateopetel.substack.com/p/between-the-manual-lab-and-the-self

## Reader experience

All six essays now have a curated, collapsible table of contents with paragraph links. These labels are stored in `content/landmarks.json`, separate from the imported source HTML. The strict build verifies that every referenced paragraph exists and refuses invalid landmarks. The complete article remains readable without JavaScript.

A small, dependency-free `reader.js` module optionally remembers the last paragraph using browser-local storage, shows a "Continue reading" link on the homepage, and displays scroll progress. Reading state stays in the visitor's browser. No account, cookie, external telemetry, or server-side reading history exists. Storage errors leave the reading experience operational.

### Audio publication gate

The site contains audio-player support but **no recordings are published yet**. Listening controls appear only for an authenticated local MP3 specified in `content/audio.json`. To add an approved recording:

1. Produce and review a complete narration against its source essay.
2. Save it as `media/<essay-slug>.mp3` within the repository.
3. Calculate `sha256sum media/<essay-slug>.mp3` and add the manifest entry, e.g.
   `"scientific-loop": {"path": "media/scientific-loop.mp3", "sha256": "<64-character SHA-256>"}`.
4. Run `python -m pytest -q`, `node --check reader.js` and `python scripts/build.py --strict --base-url https://fraware.github.io/forward-science`.
5. Confirm playback, seeking, speed control, interruption/resumption, and mobile/screen-reader operation before deployment.

The player uses native browser audio controls and restores position only through optional local storage. Navigation between independent HTML pages restarts the document, so playback itself does not continue seamlessly across page changes. Keep MP3 files compressed and monitor GitHub Pages repository and bandwidth quotas. Do not add unchecked or incomplete recordings solely to activate the Listen interface.

### Editorial requirements

Navigation landmarks are newly authored editorial aids, not reproduced section headings from the essays. Review their precise positions, labels, and implications before public release. Any future modifications to an imported article still need new provenance records; section anchors must be reviewed again following such changes.

## Offline reading editions and narration preparation

The strict build generates accessible Markdown, EPUB 3 and PDF editions from the original six verified article bodies. The exports are stored under `site/downloads/` and linked from the homepage and individual chapters. The PDF includes a linked contents section, page numbers and source references; the EPUB includes a six-chapter navigation structure. The build refuses source modifications that conflict with the recorded source hashes. No private Substack subscriber data is included.

For a future narration, run `python scripts/prepare_narration.py --out narration-work` locally. The command generates six complete UTF-8 manuscripts, paragraph-bounded narration chunks and an integrity manifest. This produces **text only**. Recordings have yet to be produced, reviewed and added to the checksum-gated audio manifest. The resulting manuscripts should be reviewed by a narrator or used with a connected voice-production provider; voice quality, scientific pronunciation and chapter completeness need listening checks before any audio is published.
