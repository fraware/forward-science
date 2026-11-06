# Publication release gate

The six-essay publication is imported from the author export and verified against recorded SHA-256 source hashes. GitHub Pages has completed its deployment and independent live-site asset-integrity checks. A paragraph-by-paragraph live Substack edition comparison, physical-device voice acceptance, and custom-domain selection remain open.

## P0 — content and editorial integrity

- [x] Identify the foundational article and five chapter publications; verify titles, subtitles, dates and URLs against the public originals.
- [x] Respect the self-described reading order, including the June 23/24 chronological inversion.
- [x] Add the sixth essay missing from the public Substack tag page.
- [x] Build six local reader routes with next/previous navigation.
- [x] Import all six original HTML bodies from the author's Substack export.
- [ ] Manually compare each imported body with the latest live edition paragraph by paragraph.
- [ ] Compare a freshly generated author export with the six committed editions using `scripts/import_substack.py --compare`; inspect all prose, links and export/provenance discrepancies. A snapshot comparison does not certify subsequent edits made on Substack.
- [ ] Complete independent live-page review. GitHub-hosted audit runs received HTTP 403 from Substack on both API and HTML routes; recorded status is `unavailable`, distinct from detected text drift. The optional public-page workflow is manual-only.
- [x] Produce an immutable-source, offline inventory of all 46 substantive links (32 distinct URLs) with paragraph anchors. This establishes completeness of link extraction, not evidence adequacy.
- [x] Produce a paragraph-level claim register for all 23 substantive paragraphs of the political-economy essay, distinguishing empirical observations, forecasts, governance proposals, and measurement claims. See `docs/POLITICAL_ECONOMY_CLAIM_REVIEW.md`. This documents the assessment, not editorial acceptance.
- [ ] Adjudicate P0 claims in the political-economy review before claiming the essay has been independently fact-checked or revised.
- [ ] Review the source-claim relevance issues recorded in `docs/EDITORIAL_EVIDENCE_AUDIT.md`, including the sequencing-core mismatch and primary-source historical chronology.
- [ ] Review footnotes, scientific citations, equations, images, media embeds, alt text and internal anchors in each chapter.
- [ ] Decide whether to correct typographical errors in the source publications; preserve a traceable edition history if changes are made.

## P0 — deployment

- [ ] Resolve domain name suitability and ownership. `forwardscience.com` is operated by an unrelated medical-device company; a third-party trademark record reports U.S. word-mark registration 5528220 (goods classes 005/010). Complete jurisdiction-appropriate naming and trademark review before selecting or promoting a custom domain. Domain availability alone does not establish freedom to use the name.
- [x] Create the dedicated GitHub repository, commit all six original essays, and verify GitHub CI and byte-for-byte file contents.
- [x] Configure a validated default GitHub Pages base URL; `SITE_BASE_URL` is optional for a future custom domain.
- [x] Configure GitHub Pages Actions deployment and complete a deployment job. Domain ownership, custom DNS, and direct HTTPS verification remain open.
- [x] Complete the strict Pages deployment after the six full-text gate passed.
- [x] Independently retrieve generated public assets via GitHub Actions and compare delivered bytes, including removed-download 404 checks (runs 41969274869 and 42119598774).
- [x] Fail closed on stale MP3s, unexpected files, and symlinks in a reused generated publication directory.
- [x] Implement a strict validator for complete private narrated-audio handoffs (original six recordings, manuscripts, independent ASR and unsigned reviewer template).
- [ ] Complete physical-device accessibility and narration playback acceptance, including iOS and Android.
- [x] Confirm dedicated Chromium browser-regression workflow on the latest `main` release ([successful run 42134299855](https://github.com/fraware/forward-science/actions/runs/42134299855)). Navigation, anchors, reader persistence, narrow layouts, and mocked speech controls were exercised in Chromium. Viewport emulation and mocked speech do not establish physical-device acceptance.
- [ ] Check canonical URLs, sitemap, indexability and external preview metadata against final domain.

## P1 — distribution

- [ ] Add the permanent site link to the original Substack collection and suitable published essays.
- [ ] Confirm social preview appearance in target platforms.
- [ ] Submit sitemap via a search index service if desired and inspect index coverage.
- [ ] Preserve original source HTML and import provenance securely.

## Verified locally

- All six original source post IDs, subtitles, and UTC publication dates were confirmed against the author's supplied export; original texts total 9,660 whitespace-delimited words.
- All six text bodies passed HTML sanitization with normalized-text preservation and recorded source/rendered SHA-256 hashes.
- A previous 14-test baseline covered source import, strict production build, provenance, metadata, and internal routes. The current GitHub release additionally runs the expanded Python suite and browser-speech tests; consult the latest CI job for its exact counts.
- All seven pages were rendered in Chromium at 1440px, 768px, 390px and 320px (28 page-width checks), with no horizontal overflow.
- A strict build with all six original bodies now passes; the no-content fixture still fails closed.
- Browser navigation is exercised in GitHub Actions using Playwright/Chromium on a loopback HTTP server; the latest main-branch run succeeded. This does not establish native iOS/Android behavior or actual voice quality.
- The public GitHub repository and CI are established. The latest main-branch Pages deployment and public-artifact audit both succeeded ([run 42134299896](https://github.com/fraware/forward-science/actions/runs/42134299896)); custom domain ownership and production indexing remain unverified. Earlier public asset integrity was independently verified in run 41969274869.
