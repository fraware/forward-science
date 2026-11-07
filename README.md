# Forward Science

Six essays on AI, scientific institutions, and the organization of discovery, by Mateo H. Petel. Originally published in June 2026.

**Read the essays:** https://fraware.github.io/forward-science/

## The publication

The series follows one argument across six texts.

1. [Forward Science](https://fraware.github.io/forward-science/forward-science/)
2. [Forward-Deployed Scientists](https://fraware.github.io/forward-science/forward-deployed-scientists/)
3. [The Unit of Deployment Is the Scientific Loop](https://fraware.github.io/forward-science/scientific-loop/)
4. [From Extension Agents to Forward-Deployed Scientists](https://fraware.github.io/forward-science/extension-agents/)
5. [Who Pays for the Scientist Who Makes Other Scientists Better](https://fraware.github.io/forward-science/political-economy/)
6. [Between the Manual Lab and the Self-Driving Lab](https://fraware.github.io/forward-science/future-laboratory/)

The original articles are also linked from the individual essay pages. The reading order follows the author's intended sequence, which differs slightly from publication-date order.

## Website

The site is built from static HTML, CSS, and a small amount of JavaScript. It uses no accounts, analytics, third-party fonts, or runtime AI services. Reading progress, if enabled by the browser, stays on the reader's device. The essays remain accessible without JavaScript.

The text in `content/essays/` comes from the author's Substack export. Its original wording is preserved, with source checksums recorded in `content/import-provenance.json`. The site renderer excludes Substack's subscription footer from the reader without changing the archived text.

Audio playback appears only for recordings with documented publication approval. The selected narration voice for the next edition is Kokoro's `am_michael` at **1.10×** synthesis speed. The current full-length recordings are under review and are not yet published.

## Build locally

Python 3.12 is used in GitHub Actions. Install the build dependencies, then serve the generated site.

```sh
python -m pip install -r requirements-build.txt
python scripts/build.py --strict --base-url https://fraware.github.io/forward-science
python -m http.server --directory site 8000
```

Open http://localhost:8000. The `site/` directory is generated and excluded from version control.

To run the test suite, install `pytest` and FFmpeg/FFprobe, then run:

```sh
python -m pytest -q
```

The separate browser checks use Playwright and Chromium. GitHub Actions validates the source, builds the site, tests navigation, deploys GitHub Pages, and checks that the public files match the deployment.

## Source and audio integrity

The complete essays are maintained in `content/essays/*.html`, with publication metadata in `content/essays.json` and navigation in `content/landmarks.json`. Source edits must be intentional and accompanied by updated provenance. Never commit a raw Substack export, which may contain subscriber information.

To check a fresh official author export without modifying the repository:

```sh
python scripts/import_substack.py /path/to/new-export.zip --compare
```

`scripts/prepare_private_export.py` helps minimize sensitive data before a private transfer. `scripts/audit_references.py` inventories links in the published texts.

Narration manuscripts come from `scripts/prepare_narration.py`. The speech-generation tools produce private review recordings. The publication build checks the final MP3 files, source-text identities, recording details, and approval record before including audio. The website does not generate speech in visitors' browsers or call an external voice API.

The four current publication decisions are tracked as [narration](https://github.com/fraware/forward-science/issues/8), [editorial corrections](https://github.com/fraware/forward-science/issues/20), [website address and indexing](https://github.com/fraware/forward-science/issues/25), and [source verification](https://github.com/fraware/forward-science/issues/26).

## Copyright

© 2026 Mateo H. Petel. The essays and site are publicly readable. No additional content-reuse or software license is granted merely by the repository being public. Third-party tools and dependencies retain their respective licenses.
