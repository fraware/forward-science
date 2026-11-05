/**
 * Browser-provided, user-initiated narration for Forward Science.
 *
 * This is distinct from the editorially reviewed MP3 audio editions. Browser
 * voices vary, and some may invoke an online service controlled by the browser.
 * No site-owned speech service, account, or telemetry is used.
 */
(function (root) {
  "use strict";

  function splitNarrationText(value, maxLength = 220) {
    if (!Number.isInteger(maxLength) || maxLength < 40) {
      throw new RangeError("maxLength must be an integer of at least 40");
    }
    let remaining = String(value).replace(/\s+/g, " ").trim();
    const chunks = [];
    while (remaining.length > maxLength) {
      const prefix = remaining.slice(0, maxLength + 1);
      let boundary = -1;
      for (const match of prefix.matchAll(/[.!?;:](?=\s)/g)) {
        if (match.index >= maxLength * 0.5) boundary = match.index + 1;
      }
      if (boundary < 0) boundary = prefix.lastIndexOf(" ");
      if (boundary < maxLength * 0.35) {
        const nextSpace = remaining.indexOf(" ", maxLength);
        boundary = nextSpace < 0 ? remaining.length : nextSpace;
      }
      chunks.push(remaining.slice(0, boundary).trim());
      remaining = remaining.slice(boundary).trimStart();
    }
    if (remaining) chunks.push(remaining);
    return chunks;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { splitNarrationText };
  }
  if (typeof document === "undefined") return;

  const panel = document.querySelector("[data-device-narration]");
  const article = document.querySelector('article[aria-label="Full essay"]');
  const slug = document.body.dataset.essaySlug;
  if (!panel || !article || !slug) return;
  const synth = root.speechSynthesis;
  const Utterance = root.SpeechSynthesisUtterance;
  if (!synth || typeof synth.speak !== "function" ||
      typeof synth.cancel !== "function" || typeof Utterance !== "function") return;

  const paragraphs = Array.from(article.querySelectorAll("p[id]"))
    .map((element) => ({
      element,
      chunks: splitNarrationText(element.textContent || ""),
    }))
    .filter((paragraph) => paragraph.chunks.length > 0);
  if (!paragraphs.length) return;

  const controls = {
    play: panel.querySelector("[data-speech-play]"),
    pause: panel.querySelector("[data-speech-pause]"),
    stop: panel.querySelector("[data-speech-stop]"),
    previous: panel.querySelector("[data-speech-previous]"),
    next: panel.querySelector("[data-speech-next]"),
    speed: panel.querySelector("[data-speech-rate]"),
    voice: panel.querySelector("[data-speech-voice]"),
    status: panel.querySelector("[data-speech-status]"),
  };
  if (Object.values(controls).some((control) => !control)) return;

  const storageKey = "forward-science:device-narration:v1:" + slug;
  const loadPosition = () => {
    try {
      const saved = JSON.parse(root.localStorage.getItem(storageKey) || "null");
      if (!saved || !Number.isInteger(saved.paragraph) || !Number.isInteger(saved.chunk)
          || saved.paragraph < 0 || saved.paragraph >= paragraphs.length
          || saved.chunk < 0 || saved.chunk >= paragraphs[saved.paragraph].chunks.length) {
        return null;
      }
      return saved;
    } catch { return null; }
  };
  const saved = loadPosition();
  // A direct section link is an explicit navigation choice and takes precedence
  // over the older listening bookmark without changing the saved voice or rate.
  function linkedParagraph() {
    const hash = root.location?.hash || "";
    return paragraphs.findIndex((paragraph) => hash === "#" + paragraph.element.id);
  }
  const deepLinkIndex = linkedParagraph();
  let paragraphIndex = deepLinkIndex >= 0 ? deepLinkIndex : saved?.paragraph ?? 0;
  let chunkIndex = deepLinkIndex >= 0 ? 0 : saved?.chunk ?? 0;
  let playbackState = saved && deepLinkIndex < 0 ? "paused" : "idle";
  let generation = 0;
  let activeUtterance = null;
  let voices = [];

  function persist() {
    try {
      root.localStorage.setItem(storageKey, JSON.stringify({
        paragraph: paragraphIndex,
        chunk: chunkIndex,
        rate: Number(controls.speed.value),
        voice: controls.voice.value,
      }));
    } catch { /* Storage is optional. */ }
  }
  function forgetPosition() {
    try { root.localStorage.removeItem(storageKey); } catch { /* Storage is optional. */ }
  }
  function report(message) { controls.status.textContent = message; }
  function updateControls() {
    controls.play.textContent = playbackState === "paused" ? "Resume" : "Play";
    controls.play.disabled = playbackState === "playing";
    controls.pause.disabled = playbackState !== "playing";
    controls.stop.disabled = playbackState === "idle";
    controls.previous.disabled = paragraphIndex === 0;
    controls.next.disabled = paragraphIndex >= paragraphs.length - 1;
    for (const [index, item] of paragraphs.entries()) {
      item.element.classList.toggle(
        "is-being-narrated", index === paragraphIndex && playbackState === "playing"
      );
    }
  }
  function cancelCurrent() {
    generation++;
    activeUtterance = null;
    synth.cancel();
  }
  function finish() {
    cancelCurrent();
    playbackState = "idle";
    paragraphIndex = 0;
    chunkIndex = 0;
    forgetPosition();
    report("Narration completed");
    updateControls();
  }
  function speakCurrent() {
    if (playbackState !== "playing") return;
    const paragraph = paragraphs[paragraphIndex];
    if (!paragraph || !paragraph.chunks[chunkIndex]) return finish();
    persist();
    const utterance = new Utterance(paragraph.chunks[chunkIndex]);
    utterance.lang = "en-US";
    utterance.rate = Number(controls.speed.value) || 1;
    const voice = voices.find((item) => item.voiceURI === controls.voice.value);
    if (voice) utterance.voice = voice;
    const ticket = generation;
    activeUtterance = utterance;
    utterance.onend = () => {
      if (ticket !== generation || activeUtterance !== utterance) return;
      activeUtterance = null;
      chunkIndex++;
      if (chunkIndex >= paragraph.chunks.length) {
        paragraphIndex++;
        chunkIndex = 0;
      }
      if (paragraphIndex >= paragraphs.length) return finish();
      report("Listening — paragraph " + (paragraphIndex + 1) + " of " + paragraphs.length);
      updateControls();
      speakCurrent();
    };
    utterance.onerror = (event) => {
      if (ticket !== generation || activeUtterance !== utterance) return;
      // Our own cancel operations invalidate the generation first. Any error
      // still associated with the current utterance, including interruption
      // or cancellation by the browser, must release the Play control.
      activeUtterance = null;
      playbackState = "paused";
      persist();
      const reason = event?.error;
      report(reason === "interrupted" || reason === "canceled"
        ? "Narration interrupted. Select Resume to continue."
        : "Your browser could not continue. Try Resume or another voice.");
      updateControls();
    };
    try {
      synth.speak(utterance);
    } catch {
      activeUtterance = null;
      playbackState = "paused";
      report("Narration is unavailable with this browser voice.");
      updateControls();
    }
  }
  function begin() {
    if (playbackState === "playing") return;
    cancelCurrent();
    playbackState = "playing";
    report("Listening — paragraph " + (paragraphIndex + 1) + " of " + paragraphs.length);
    updateControls();
    speakCurrent();
  }
  function pause() {
    if (playbackState !== "playing") return;
    // Restart the current short phrase on Resume. Browser pause APIs differ.
    cancelCurrent();
    playbackState = "paused";
    persist();
    report("Paused — paragraph " + (paragraphIndex + 1) + " of " + paragraphs.length);
    updateControls();
  }
  function stop() {
    cancelCurrent();
    playbackState = "idle";
    paragraphIndex = 0;
    chunkIndex = 0;
    forgetPosition();
    report("Narration stopped");
    updateControls();
  }
  function seekParagraph(offset) {
    const next = Math.max(0, Math.min(paragraphs.length - 1, paragraphIndex + offset));
    if (next === paragraphIndex) return;
    const wasPlaying = playbackState === "playing";
    cancelCurrent();
    paragraphIndex = next;
    chunkIndex = 0;
    playbackState = wasPlaying ? "playing" : "paused";
    persist();
    report((wasPlaying ? "Listening" : "Ready") + " — paragraph "
      + (paragraphIndex + 1) + " of " + paragraphs.length);
    updateControls();
    if (wasPlaying) speakCurrent();
  }
  function populateVoices() {
    let available = [];
    try { available = synth.getVoices?.() || []; } catch { /* Use browser default. */ }
    voices = available.filter((voice) => /^en(?:-|$)/i.test(voice.lang || ""))
      .sort((a, b) => Number(b.localService) - Number(a.localService)
        || a.name.localeCompare(b.name));
    const current = controls.voice.value || saved?.voice || "";
    controls.voice.replaceChildren();
    const automatic = document.createElement("option");
    automatic.value = "";
    automatic.textContent = "Browser default";
    controls.voice.appendChild(automatic);
    for (const voice of voices) {
      const option = document.createElement("option");
      option.value = voice.voiceURI;
      option.textContent = voice.name + " (" + voice.lang
        + (voice.localService ? ", local" : "") + ")";
      controls.voice.appendChild(option);
    }
    controls.voice.value = voices.some((voice) => voice.voiceURI === current) ? current : "";
  }

  if (saved && [0.75, 1, 1.25, 1.5, 2].includes(saved.rate)) {
    controls.speed.value = String(saved.rate);
  }
  populateVoices();
  synth.addEventListener?.("voiceschanged", populateVoices);
  controls.play.addEventListener("click", begin);
  controls.pause.addEventListener("click", pause);
  controls.stop.addEventListener("click", stop);
  controls.previous.addEventListener("click", () => seekParagraph(-1));
  controls.next.addEventListener("click", () => seekParagraph(1));
  for (const selector of [controls.speed, controls.voice]) {
    selector.addEventListener("change", () => {
      if (playbackState === "playing") {
        cancelCurrent();
        speakCurrent();
      }
      if (playbackState !== "idle") persist();
    });
  }
  root.addEventListener("pagehide", () => {
    // Browsers can retain this document in the back/forward cache. Canceling
    // speech without updating state leaves Play disabled on restoration.
    // Pause explicitly, retaining the current short-phrase boundary.
    if (playbackState === "playing") pause();
  });
  root.addEventListener("hashchange", () => {
    const selected = linkedParagraph();
    if (selected < 0 || selected === paragraphIndex) return;
    // A section jump changes the listening target but never initiates speech.
    if (playbackState === "playing") {
      cancelCurrent();
      playbackState = "paused";
    }
    paragraphIndex = selected;
    chunkIndex = 0;
    persist();
    report("Ready to listen — paragraph " + (paragraphIndex + 1)
      + " of " + paragraphs.length);
    updateControls();
  });
  report(saved && deepLinkIndex < 0 ? "Ready to resume — paragraph " + (paragraphIndex + 1)
    + " of " + paragraphs.length
    : "Ready to listen — paragraph " + (paragraphIndex + 1)
      + " of " + paragraphs.length);
  updateControls();
  panel.hidden = false;
})(typeof window !== "undefined" ? window : globalThis);
