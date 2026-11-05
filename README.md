# Forward Science

A typography-first, dependency-free static website for the six Forward Science publications by Mateo H. Petel, originally published June 22–27, 2026.

**Editorial sequence:** The foundational essay (`00`), then five chapters (`01–05`). The first and second chapters explicitly identify their order in the original articles; their publication dates run in a different order. The concluding essay is absent from the Substack tag listing but was verified at its standalone publication URL.

## Current state

- Homepage and six local chapter routes are generated from one verified `content/essays.json` manifest.
- All six full-length essays have been imported from the author's official November 2026 Substack export, including the final essay missing from the Substack tag page. They are available as local reading pages.
- The original essay prose is **never paraphrased by the importer**. Permitted HTML elements are retained and active content is removed; a text-equivalence check fails closed on changed prose. The strict build checks each imported body against its recorded SHA-256 hash.
- The original export contained unrelated posts, subscriber information, and delivery analytics. None of those private files were copied into this project. Only six sanitized article bodies and their bounded provenance metadata are included.
- The importer and strict deployment workflow refuse to pass partial or ambiguous imports as complete texts. Deployment runs on pushes to `main` and by manual dispatch; continuous integration runs on pushes and pull requests.
- **Publication status:** The complete publication is committed to `fraware/forward-science`. A GitHub Pages deployment job completed successfully on November 3, 2026 (UTC). The GitHub Pages public HTTP release was independently verified in deployment run 41969274869. Live-Substack paragraph comparison and custom-domain selection remain open.

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

Visit `http://localhost:8000`. The website includes optional local-state reader controls and browser speech in dependency-free JavaScript; the six essays remain readable with JavaScript disabled. There are no analytics, remote fonts, accounts, or server-side application requirements.

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

GitHub Actions reports a successful deployment. The public address was independently inspected and matched against every expected generated asset in GitHub Pages deployment run 41969274869; final Substack edition comparison and domain selection remain necessary before announcing the publication. Never commit subscriber exports or unrelated analytics.

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

## Author-only edition exports and narration preparation

The website intentionally contains no offline-download section or chapter download controls. The strict GitHub Pages build excludes PDF, EPUB and Markdown artifacts and removes old `site/downloads/` files from a reused local build directory. The separate source-verified exporter remains available for private publication work with `python scripts/export_editions.py --out /path/outside/site`. Generated files must remain outside `site/` to avoid accidental public deployment. No private Substack subscriber data is included.

For a future narration, run `python scripts/prepare_narration.py --out narration-work` locally. The command generates six complete UTF-8 manuscripts, paragraph-bounded narration chunks and an integrity manifest. This produces **text only**. Recordings have yet to be produced, reviewed and added to the checksum-gated audio manifest. The resulting manuscripts should be reviewed by a narrator or used with a connected voice-production provider; voice quality, scientific pronunciation and chapter completeness need listening checks before any audio is published.

## Browser-voice listening

The site presents an optional **Listen** interface in browsers that support Web Speech synthesis and lack an approved MP3 recording for the essay. The browser supplies the voice. Available voices, their pronunciation and reliability differ by device, and some browser voices use online services. Browser narration is clearly distinguished from an editorially reviewed recording.

Playback starts only on an explicit Play action. Readers choose speed and browser voice, pause and resume at short phrase boundaries, or move through original essay paragraphs. Position is stored optionally in browser-local storage; failures to access storage leave listening functional. No website-operated audio service or tracking is involved. Unsupported browsers retain the original reading experience with the control hidden. A reviewed MP3 recording, once available and SHA-256 validated, supersedes browser narration for its essay.

Automated checks use mock speech engines; real voice quality and background playback on phones remain external acceptance criteria.


### Browser narration interruption handling

If the browser stops speech unexpectedly, the Listen controls enter an explicit paused state and retain the last short-phrase boundary. The reader can resume without encountering a disabled Play button. A `pagehide` event also pauses active speech to keep back/forward-cache restoration consistent. User-triggered Stop clears the saved position, while interrupted/paused playback retains it. These transitions are covered by simulated Web Speech regression tests; physical-device narration quality and background behavior still require external validation.


### Linked-section listening

Direct chapter links with a valid paragraph fragment (for example, `#p-03`) select the corresponding starting paragraph for browser narration, taking precedence over the older saved listening position. Switching sections using an in-essay anchor while audio is playing pauses narration, preserves the new position, and waits for an explicit Resume action. Invalid fragments are ignored. No navigation event triggers autoplay.


## Definitive MP3 release policy

Browser speech synthesis remains available as a progressive enhancement.
Professionally narrated MP3 editions are published only after the author
or another accountable reviewer has listened to each full recording, compared
it with the source manuscript, checked scientific pronunciations and sound
quality, and confirmed distribution rights.

A record under `content/audio.json` must contain:

```json
{
  "scientific-loop": {
    "path": "media/scientific-loop.mp3",
    "sha256": "<sha256 of final MP3 bytes>",
    "manuscript_sha256": "<sha256 from narration-work/manifest.json>",
    "voice": {
      "type": "human",
      "name": "<actual voice or narrator>",
      "provider": "<actual provider>",
      "distribution_rights_basis": "<documented rights>"
    },
    "review": {
      "reviewer": "<actual reviewer>",
      "reviewed_on": "YYYY-MM-DD",
      "listened_in_full": true,
      "spoken_text_checked": true,
      "pronunciation_checked": true,
      "audio_artifacts_checked": true,
      "distribution_rights_confirmed": true
    }
  }
}
```

Use the real voice type (`human` or `synthetic`) and record the actual
provider and permission to redistribute the recordings. Never invent
attestations. Run `python scripts/verify_audio.py`; a strict site build
invokes the same verifier whenever a recording is listed. It checks SHA-256,
the source narration manuscript, reviewer fields, one MP3 stream, plausible
duration and audio format, and full-file FFmpeg decoding. FFmpeg and FFprobe
must be installed for actual MP3 publication. These automated checks do
not prove audio-to-text correspondence or artistic quality; that judgment
remains the stated human sign-off.

The manifest is currently empty. No MP3 recordings have passed the gate.


### Narration mastering and review cues

Full-length synthetic draft production now applies FFmpeg loudness normalization directly from each source PCM WAV to approximately **-18 LUFS** with a **-1.5 dBTP** target, 24 kHz mono and 96 kbps MP3. After encoding, a separate decoding/measurement step rejects out-of-range loudness, excessive true peak and silent gaps longer than 2.5 seconds. The source-faithful segment manifest includes approximate per-phrase start/end times, paragraph numbers, and source-text hashes. These cues help the human reviewer locate difficult scientific terms and transitions; MP3 encoder padding means they are not sample-exact alignments. Silence, peak and loudness checks do not verify spoken correctness. The editorially reviewed MP3 release gate remains unchanged.


### Independent master-quality check for definitive recordings

The strict public MP3 gate independently measures each approved file with FFmpeg using EBU R128 loudness analysis. It rejects recordings outside -21 to -15 LUFS, true peak above -1 dBTP, or unexplained silent gaps of four seconds or longer. Tests exercise real MP3 decoding and real loudness measurement. These are technical consistency checks alongside, not substitutes for, complete human listening and text fidelity review.


### Voice artifact reproducibility and disclosure

The six-essay synthetic candidate generator verifies the exact SHA-256 values
of the Kokoro ONNX backbone and the v1.0 voice pack used in the successful
initial and remastered runs. Updated upstream model files require an explicit
reviewed checksum change before synthesis. The website's native MP3 player
identifies an approved edition as **synthetic** or **human** narration, with its
actual voice name and provider, and presents the essay as its written transcript.
This disclosure applies only if a recording passes the separate strict-release
gate; the public audio manifest currently remains empty.


### Public MP3 delivery integrity

For any future approved MP3 release, the post-deployment GitHub Pages audit
downloads the actual public narration bytes and compares SHA-256 with the
approved build artifact. Large non-audio files retain lighter HEAD checks.
This catches audio substitutions that preserve file length; it adds bandwidth
only to a publication carrying approved recordings. Public MP3 playback is
still absent until recorded-text and listening review pass.


### Independent narration-discrepancy triage

The independent ASR audit reports both raw word error rate and an additional
conservative content-edit estimate. Orthographic splitting or joining (such as
`first hand` → `firsthand`) no longer counts as substantive drift, while
homophones, omitted qualifications, inflections, unusual terminology and
ASR-uncertain phrases remain in the listening queue. **Every content mismatch
is included in the review queue, even with low estimated WER.** This is
prioritization only: audio-to-text comparison is not a substitute for
full-length listening. The original manuscript, recorded audio and ASR
transcripts remain independently versioned and unapproved until sign-off.


## Controlled six-essay audio publication handoff

`scripts/stage_reviewed_audio.py` converts **private**, explicit human review
evidence into a staged release bundle. The original draft archive and
independent `ASR_AUDIT_UNREVIEWED.json` must match by SHA-256. Export notes from
the private ASR-assisted listening interface; its JSON must identify all six
exact MP3s, mark each `__fullListened: true`, and mark every ASR-flagged phrase
`checked` with a substantive adjudication note. Any unresolved `problem`
blocks staging.

Begin with `docs/narration-approval.template.json` (all approval flags initially false). Create a private copy outside Git after carrying out the listed reviews.

A separate reviewer-authored `approval.json` must include a genuine
`authorize_release_candidate: true`, actual reviewer and ISO review date,
the voice provenance (`type: synthetic`, `name: af_heart`, provider, specific
distribution-rights basis), and five honestly asserted boolean `attestations`
(`listened_in_full`, `spoken_text_checked`, `pronunciation_checked`,
`audio_artifacts_checked`, `distribution_rights_confirmed`). Never
fabricate the reviewer details or a listening judgment.

```bash
python scripts/stage_reviewed_audio.py --source . \
  --drafts /private/unreviewed-drafts \
  --asr /private/asr/ASR_AUDIT_UNREVIEWED.json \
  --notes /private/forward-science-narration-review-notes.json \
  --approval /private/approval.json \
  --output /private/release-staging
```

A successful run re-verifies all six audio/source hashes, review coverage,
reviewer declarations, FFmpeg full-file decoding, codec, duration, loudness,
peak and long-silence thresholds. It produces a private `media/` directory,
`audio.json` for later copying into `content/`, and a provenance receipt.
It **does not modify the Git repository or public site**. A reviewed Git
commit and passing production deployment remain mandatory for publication.


### Public-artifact hygiene

Every strict build now rejects unexpected output files, symbolic links, and
output paths overlapping authoritative source directories. Reusing a local
site directory automatically retracts stale `site/media/` content, including
previously approved MP3 files subsequently withdrawn from the manifest.
This matters for local and custom-hosting builds even though GitHub Actions
usually checks out into a clean runner. Public download editions remain
excluded. CI includes regression tests covering stale-media withdrawal,
unrecognized private files, symlink safety, and protected source paths.
