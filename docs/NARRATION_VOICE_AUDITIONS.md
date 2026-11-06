# Forward Science — Natural narrator selection and publication gate

**Status:** editorial decision and sample generation; no recording approved for publication.

The discontinued website narration relied on the reader's browser-provided speech engine. Its pronunciation, prosody, accents, and consistency were outside the publication's control. The user assessed the available voices as unacceptably artificial. **The site now loads only explicitly approved, source-verified MP3 recordings.** There is no runtime text-to-speech service, API credential, external voice widget, or autoplay.

## Preferred alternatives

| Provider | Narration approach | Payment / rights | Practical conclusion |
| --- | --- | --- | --- |
| **ElevenLabs Multilingual v2** | Stable, expressive prerecorded long-form speech with a single selected voice. Newer Eleven v4 is a separate audition candidate. | The advertised Creator plan is **$22/month, $11 introductory first month, 121k credits** as checked November 2026. Paid plans include commercial rights subject to terms and voice permissions. Prices and credit use may change. | **Best paid evaluation candidate** if its voice is audibly preferable and recurring license/quality obligations are accepted. |
| **Kokoro-82M**, open-weight model | Four locally generated voice auditions; the existing private draft pipeline supports complete mastered recordings. | Apache-2.0 upstream model and distribution, no per-character API bill. Compute and quality review still have costs. | **Best zero-subscription candidate**. Do not assume equal naturalness or scientific pronunciation without listening. |
| **Browser Web Speech** | Live system voice. | Browser- and OS-dependent. | **Retired from Forward Science's UI**; user can use separate accessibility software. |

Primary documentation: [ElevenLabs plans](https://elevenlabs.io/pricing), [ElevenLabs model selection](https://elevenlabs.io/docs/overview/capabilities/text-to-speech), [ElevenLabs usage rights](https://elevenlabs.io/docs/overview/capabilities/text-to-speech), and [upstream Kokoro voice samples and Apache-2.0 model](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX).

## Collection size and budgeting

All six essays together contain approximately **67,250 spoken characters**, excluding their Substack subscription widgets, and around **9,600 words**. Counts are approximate and can change with approved editorial revisions.

ElevenLabs' current advertised per-character usage is approximately 1 credit for Multilingual v2. A single pass would use approximately 67,250 credits, plus a reserve for short tests, regenerations, punctuation improvements and corrections. Its free allowance of 10k and Starter's 30k monthly credits are insufficient for one full standard-rate pass. Creator's 121k credits are more suitable for a complete standard-rate pass **with limited revision headroom**, subject to actual product pricing and voice/model charging rules. The discounted Flash v2.5 API model has a different credit rate; it must be separately evaluated for voice quality.

Generate once and serve the final reviewed MP3 as a static site file. Do not send paragraphs to a paid API each time a reader clicks Play. Keep API credentials outside source control and the browser.

## Additional open-weight models for an independent audition

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) has Apache-2.0-licensed 0.6B and 1.7B speech models, including English preset voices. It is a credible additional option to test for greater naturalness, with substantially higher inference and memory needs than Kokoro 82M. Its developers publish quality results, yet selection for Forward Science must rely on **identical-text listening tests and scientific pronunciation audits**, not vendor/developer benchmarks alone.

[Chatterbox](https://github.com/resemble-ai/chatterbox) is MIT open source but was archived as unmaintained research in August 2026. It remains a possible offline comparison, with an extra operational-maintenance risk. Never clone any person's voice without their permission.

## Four free, comparable narrator auditions

The source-controlled workflow [narration-voice-auditions.yml](../.github/workflows/narration-voice-auditions.yml) synthesizes identical passages from the source-verified first essay with four pinned Kokoro voices:

- `af_heart` — American female.
- `bf_emma` — British female.
- `am_michael` — American male.
- `bm_george` — British male.

Each sample uses the same model and text SHA-256. The GitHub Actions workflow verifies model and voice-pack hashes; creates short **unreviewed** MP3s and per-voice provenance JSON; asserts all four samples use the identical narration text; and uploads one 30-day editorial artifact, **FOUR-VOICE-UNREVIEWED-NARRATION-AUDITIONS**. The samples are not deployed to the website or eligible for publication. Workflow execution depends on normal GitHub Actions availability.

To reproduce locally, install the specified runtime and use `scripts/generate_narration_candidate.py` with pinned Kokoro model assets and your chosen `--voice` value. The six-essay unreviewed master production workflow and all-source integrity gates already exist; do not regenerate all six until a narrator has been chosen.

## Editorial listening rubric

Reviewers should listen to **all** samples over headphones at 1x speed, preferably on desktop and mobile:

1. **Naturalness:** steady humanlike cadence, appropriate sentence-level emphasis, varied but controlled prosody, absence of robotic monotony or theatrical overacting.
2. **Scientific fidelity:** names, acronyms, numbers, units, institutions, and technical phrases pronounced accurately; no invented words, dropped negations or altered scientific terms.
3. **Structure:** believable transitions across commas, full stops, headings and paragraph boundaries without synthetic pauses or clipped endings.
4. **Clarity and listener fatigue:** intelligibility in dense prose over several minutes, consistent spectral character and loudness, minimal distortion.
5. **Repeatability:** one coherent narrator across all six essays; no voice drift between paragraphs, changes in pitch, or missing content.

A preferred short audition does **not** validate a complete recording. For a chosen voice, prepare all six full-length, source-hashed MP3s privately, run the independent ASR mismatch review, inspect waveform and loudness/silence checks, listen **in full** to every chapter, confirm redistribution rights, and produce genuine signed-off editorial metadata. The existing `scripts/stage_reviewed_audio.py` and `scripts/verify_audio.py` release gates enforce checksums and reviewer attestations, though a human remains responsible for the audio quality judgment.

## Follow-on paid comparison

The [manual-only ElevenLabs voice audition workflow](../.github/workflows/elevenlabs-audition.yml) defaults to **no-charge preview mode**. A selected narrator is sent one short source-identical passage only through an explicit paid execution flag. Samples and source/voice checksums remain private and unreviewed.

Equivalent local commands:

```bash
# Default: no external request and no credits spent.
python scripts/generate_elevenlabs_audition.py --output /private/fs-elevenlabs-plan

# Optional deliberate paid sample; set API key securely, never in a repo.
python scripts/generate_elevenlabs_audition.py \
  --output /private/fs-elevenlabs-sample \
  --voice-id JBFqnCBsd6RMkjVDRZzb \
  --max-credits 2000 --execute
```

The official ElevenLabs documentation uses that voice identifier as an example; it is not the editorially chosen narrator. The first two paragraphs and their SHA-256 match the Kokoro audition input. The CLI verifies the full source manuscript hash, validates response size and MP3 codec/duration, records the provider/model/voice and never writes the secret. The credit ceiling is a **one-credit-per-character estimate** for Multilingual v2, not a billing authorization for anything beyond the specified request; examine actual account usage after synthesis. Avoid automatic retries following ambiguous HTTP failures because generation might already have incurred a charge.

For the GitHub workflow, use `Settings → Secrets and variables → Actions` to store `ELEVENLABS_API_KEY` privately. Enter the voice ID and select the billable checkbox for an authorized sample; the default is false. Neither running the script nor obtaining an MP3 constitutes approval to distribute the narration.


If none of the free voices is acceptable, audition **ElevenLabs Multilingual v2** first, comparing the **same** source passage against one or two voices chosen from the service's library. The provider documents Multilingual v2 as the most stable model for long-form narration. The newer v4 may be sampled for expressiveness, without assuming that a more dramatic voice is preferable for a scientific essay.

Starting voice-settings for a controlled test are stability around 0.5–0.65, similarity around 0.75, and style at zero; the appropriate voice matters more than small parameter changes. These are candidate settings, not verified optimal values. Use a pronunciation dictionary where supported and check generated speech against the original article. Confirm model/voice license, commercial rights, monthly credits, and consent for any voice clone **before** using a file publicly.

**Release decision:** Continue the text-only public edition until complete, accurately spoken audio passes accountable human listening review. The new free auditions provide a way to make that decision by actual listening rather than by provider marketing.
