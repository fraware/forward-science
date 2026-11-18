# Forward Science: search and agent discovery

This document describes the publication's discovery contract and the external
steps needed to measure actual search visibility. The six essays remain the
source of substantive claims. Metadata is generated from their verified
manifest and imported-source provenance.

## Current technical publication contract

- Seven human-readable HTML pages: one collection page and six complete essays.
- Self-referential canonical URLs under the configured HTTPS `SITE_BASE_URL`.
- Original Substack article links on every essay page.
- `WebSite`, `CollectionPage`, `CreativeWorkSeries`, `ItemList`, `Person`,
  `Article`, `WebPage`, and `BreadcrumbList` Schema.org graphs. Article
  publication dates use the manifest; no invented modification dates.
- Topic-specific HTML and Open Graph descriptions derived from editorial
  summaries; no fabricated endorsements, reviews, or scientific results.
- `/forward-science/llms.txt` relative to the GitHub Pages project base:
  optional concept-to-source navigation for agents. Google says this format
  does not improve Google Search visibility.
- An Atom feed with original publication timestamps from
  `content/import-provenance.json`, and both website and Substack links.
- A sitemap and open `robots.txt` emitted only for the complete collection.
- Strict deployment validation and generated-output allowlists include the
  discovery assets. Automated tests check source correspondence.

**Important hosting constraint:** This is a GitHub Pages *project* site.
The origin-level robots control file is `https://fraware.github.io/robots.txt`,
not `https://fraware.github.io/forward-science/robots.txt`. The file published
under the project subpath is informational and is not the host's authoritative
robots exclusion policy. No crawl disallow rules are needed for this public
collection. Sitemap submission through webmaster tools is essential for
explicit discovery; the project-path robots file alone is insufficient.

The HTML document title remains exactly `Forward Science` as requested,
including on individual essays. Distinct article-specific title elements
would ordinarily improve organic search result differentiation. This is a
deliberate tradeoff to preserve the agreed browser-tab title. Individual
essays retain unique H1 headings, URLs, summaries, and Open Graph titles.

## Steps needing external publisher or search-console access

1. Verify the URL-prefix property
   `https://fraware.github.io/forward-science/` in Google Search Console.
   Inspect all seven URLs and submit
   `https://fraware.github.io/forward-science/sitemap.xml`. Confirm that Google
   considers each intended URL indexed and inspect the Google-selected
   canonical, not only the user-declared canonical.
2. Verify the corresponding site in Bing Webmaster Tools and submit the same
   sitemap. Check crawl/index reports for all seven URLs.
3. Add a natural editorial link from the Critical Systems series landing page
   to the complete Forward Science collection. Where editing the six original
   posts is appropriate, include a consistent "Read the complete series" link
   to the website. Retain original source URLs and bylines. Do not change
   original-article canonicalization blindly.
4. Link to the collection from authoritative author-controlled profiles where
   appropriate, including the author's personal homepage and publication
   profile. Avoid purchased links, link networks, or synthetic citations.
5. Measure Google Search Console impressions, clicks, click-through rate,
   indexing state, page-level search queries, and canonical-selection issues.
   Example diagnostic phrases: "Forward Science",
   "forward-deployed scientist", "forward deployed scientists",
   "deployed scientist", "scientific loop", and "AI for science".
   Treat impressions and actual citations separately.
6. Review the structure of citations to individual essays in external
   scholarly or policy writing. Use direct essay URLs and accurate summaries
   instead of repeating promotional descriptions. Monitor whether external
   references attribute ideas to the author and link back to the relevant
   essay, with the original Substack source available alongside it.

## Constraints and interpretation

A website and its Substack originals contain overlapping essay text.
Search engines independently determine their selected canonical URL for
duplicate clusters. Self-canonical markup is a signal, not a guarantee of
indexing or preferential ranking. The collection landing page supplies a
distinct reference destination, while original posts preserve publication
history.

Machine-readable metadata helps parsers locate and interpret the essays.
It does not establish that future agents will ingest the site, cite the work,
or treat its arguments as scientific consensus. The author's own essays are
primary sources for the coined terminology, not independent confirmation of
empirical or institutional claims.

Do not introduce artificial reviews, invented affiliations, unsupported
`dateModified` values, keyword-stuffed text, fabricated backlinks, or new
"AI optimization" endpoints without demonstrated consumer need.

## Release checks

```bash
python -m pip install -r requirements-build.txt pytest
python -m pytest -q -rs
python scripts/build.py --strict --base-url https://fraware.github.io/forward-science
test -s site/sitemap.xml
test -s site/feed.xml
test -s site/llms.txt
```

The Pages workflow also compares every public file with its generated
release artifact. A successful build and successful public-byte comparison
establish deployed consistency, not search-engine indexing.
