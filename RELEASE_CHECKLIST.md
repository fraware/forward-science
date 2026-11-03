# Publication release gate

The six-essay publication is imported from the author export and verified against recorded SHA-256 source hashes. GitHub Pages completed its initial deployment job on November 3, 2026 (UTC). Independent live-site HTTP checks, final Substack edition comparison, and custom-domain selection remain open.

## P0 — content and editorial integrity

- [x] Identify the foundational article and five chapter publications; verify titles, subtitles, dates and URLs against the public originals.
- [x] Respect the self-described reading order, including the June 23/24 chronological inversion.
- [x] Add the sixth essay missing from the public Substack tag page.
- [x] Build six local reader routes with next/previous navigation.
- [x] Import all six original HTML bodies from the author's Substack export.
- [ ] Manually compare each imported body with the latest live edition paragraph by paragraph.
- [ ] Review footnotes, scientific citations, equations, images, media embeds, alt text and internal anchors in each chapter.
- [ ] Decide whether to correct typographical errors in the source publications; preserve a traceable edition history if changes are made.

## P0 — deployment

- [ ] Resolve domain name suitability and ownership.
- [x] Create the dedicated GitHub repository, commit all six original essays, and verify GitHub CI and byte-for-byte file contents.
- [x] Configure a validated default GitHub Pages base URL; `SITE_BASE_URL` is optional for a future custom domain.
- [x] Configure GitHub Pages Actions deployment and complete a deployment job. Domain ownership, custom DNS, and direct HTTPS verification remain open.
- [x] Complete the strict Pages deployment after the six full-text gate passed.
- [ ] Independently inspect the deployed site, test chapter navigation and critical source links.
- [ ] Check canonical URLs, sitemap, indexability and external preview metadata against final domain.

## P1 — distribution

- [ ] Add the permanent site link to the original Substack collection and suitable published essays.
- [ ] Confirm social preview appearance in target platforms.
- [ ] Submit sitemap via a search index service if desired and inspect index coverage.
- [ ] Preserve original source HTML and import provenance securely.

## Verified locally

- All six original source post IDs, subtitles, and UTC publication dates were confirmed against the author's supplied export; original texts total 9,660 whitespace-delimited words.
- All six text bodies passed HTML sanitization with normalized-text preservation and recorded source/rendered SHA-256 hashes.
- Fourteen automated tests passed, including sanitized export import, strict production build, provenance tamper detection, metadata, and internal route validation.
- All seven pages were rendered in Chromium at 1440px, 768px, 390px and 320px (28 page-width checks), with no horizontal overflow.
- A strict build with all six original bodies now passes; the no-content fixture still fails closed.
- Full browser navigation could not be exercised in this environment because network and file navigation are administratively restricted; internal route targets were separately verified via automated tests.
- The public GitHub repository and CI are established. The first Pages deployment job succeeded. Custom domain, independent live HTTP inspection and production indexing remain unverified.
