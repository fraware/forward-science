# Forward Science

A typography-first, dependency-free static website for the six Forward Science publications by Mateo H. Petel, originally published June 22–27, 2026.

**Editorial sequence:** The foundational essay (`00`), then five chapters (`01–05`). The first and second chapters explicitly identify their order in the original articles; their publication dates run in a different order. The concluding essay is absent from the Substack tag listing but was verified at its standalone publication URL.

## Current state

- Homepage and six local chapter routes are generated from one verified `content/essays.json` manifest.
- All six full-length essays have been imported from the author's official November 2026 Substack export, including the final essay missing from the Substack tag page. They are available as local reading pages.
- The original essay prose is **never paraphrased by the importer**. Permitted HTML elements are retained and active content is removed; a text-equivalence check fails closed on changed prose. The strict build checks each imported body against its recorded SHA-256 hash.
- The original export contained unrelated posts, subscriber information, and delivery analytics. None of those private files were copied into this project. Only six sanitized article bodies and their bounded provenance metadata are included.
- The importer and strict deployment workflow refuse to pass partial or ambiguous imports as complete texts. The deployment workflow runs only by explicit manual dispatch; continuous integration runs on pushes and pull requests.
- **Publication status:** The full-text static website is built and tested locally. It has not yet been committed to a dedicated repository or deployed to a verified custom domain. Paragraph-by-paragraph comparison with current public Substack copies is still a manual editorial acceptance task.

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

1. Choose and legally assess a unique domain. `forwardscience.com` is occupied by a different organization.
2. Create a repository for this project. Install the generated `site/` folder as the GitHub Pages artifact (the workflow does this).
3. Confirm the six imported full-text HTML files and `content/import-provenance.json` are versioned, without uploading the original private export.
4. In repository **Settings → Secrets and variables → Actions → Variables**, set `SITE_BASE_URL` to the exact HTTPS production URL, e.g. `https://USER.github.io/forward-science` or a verified custom domain.
5. In repository **Settings → Pages**, choose **GitHub Actions** as the source. The workflow intentionally fails before deploy until all six imported texts and `SITE_BASE_URL` are present.
6. For a custom domain, verify domain ownership and configure its DNS according to GitHub Pages guidance. Enable HTTPS. Change the repository variable to the final domain and redeploy.
7. Audit the deployed pages, canonical tags, sitemap, social previews and search indexing. Once correct, link the original Substack publications to the new site.

See `RELEASE_CHECKLIST.md` for the release gate and content-level editorial checks.

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