/**
 * Progressive reading enhancement for the static Forward Science publication.
 * No account, analytics, cookies or network activity. All storage is optional.
 */
(() => {
  "use strict";
  const KEY = "forward-science:reading:v1";
  const audioKey = (slug) => "forward-science:audio:v1:" + slug;
  const readState = () => {
    try {
      const raw = localStorage.getItem(KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch { return null; }
  };
  const store = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
  };
  const slug = document.body.dataset.essaySlug;
  if (!slug) {
    const panel = document.getElementById("continue-reading");
    const link = document.getElementById("continue-reading-link");
    const clear = document.getElementById("clear-reading-progress");
    const state = readState();
    if (panel && link && state && typeof state.slug === "string"
        && /^[a-z][a-z0-9-]*$/.test(state.slug)
        && /^p-\d{2,3}$/.test(state.paragraph || "")) {
      link.href = state.slug + "/#" + state.paragraph;
      link.textContent = "Continue " + (state.title || "the last essay");
      panel.hidden = false;
      clear?.addEventListener("click", () => {
        try { localStorage.removeItem(KEY); } catch { /* storage optional */ }
        panel.hidden = true;
      });
    }
    return;
  }

  const article = document.querySelector('article[aria-label="Full essay"]');
  if (!article) return;
  const paragraphs = Array.from(article.querySelectorAll("p[id]"));
  const track = document.querySelector(".reading-progress span");
  const resume = document.querySelector(".resume-reading");
  const citation = document.querySelector(".copy-citation");
  const status = document.querySelector(".reader-status");
  const title = document.querySelector(".chapter-heading h1")?.textContent?.trim() || "essay";
  const prior = readState();
  if (prior?.slug === slug && prior.paragraph && document.getElementById(prior.paragraph)) {
    resume.hidden = false;
    resume.addEventListener("click", () => {
      document.getElementById(prior.paragraph)?.scrollIntoView({ behavior: "smooth", block: "start" });
      resume.hidden = true;
    });
  }

  let lastParagraph = "";
  let ticking = false;
  const update = () => {
    ticking = false;
    const top = article.getBoundingClientRect().top + window.scrollY;
    const bottom = article.getBoundingClientRect().bottom + window.scrollY;
    const position = window.scrollY + window.innerHeight * 0.38;
    const fraction = Math.min(1, Math.max(0, (position - top) / Math.max(1, bottom - top)));
    if (track) track.style.width = (fraction * 100).toFixed(1) + "%";
    if (position < top || paragraphs.length === 0) return;
    let current = paragraphs[0];
    for (const p of paragraphs) {
      if (p.getBoundingClientRect().top <= window.innerHeight * 0.38) current = p;
      else break;
    }
    if (current.id !== lastParagraph) {
      lastParagraph = current.id;
      store(KEY, { slug, paragraph: current.id, title, updated: Date.now() });
    }
  };
  const schedule = () => {
    if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
  };
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  schedule();

  citation?.addEventListener("click", async () => {
    const value = citation.dataset.citation;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      if (status) status.textContent = "Citation copied";
    } catch {
      if (status) status.textContent = "Select the page URL to share this essay";
    }
  });

  const audio = document.querySelector("audio[data-audio-for]");
  const speed = document.querySelector(".audio-speed");
  if (!audio) return;
  const savedAudio = (() => {
    try { return JSON.parse(localStorage.getItem(audioKey(slug)) || "null"); }
    catch { return null; }
  })();
  audio.addEventListener("loadedmetadata", () => {
    if (savedAudio && Number.isFinite(savedAudio.time) && Number.isFinite(audio.duration)
        && savedAudio.time > 0 && savedAudio.time < audio.duration - 5) {
      audio.currentTime = savedAudio.time;
    }
  }, { once: true });
  audio.addEventListener("timeupdate", () => {
    if (Number.isFinite(audio.currentTime) && audio.currentTime >= 0) {
      store(audioKey(slug), { time: audio.currentTime });
    }
  });
  audio.addEventListener("ended", () => store(audioKey(slug), { time: 0 }));
  speed?.addEventListener("change", () => {
    const chosen = Number(speed.value);
    if ([0.75, 1, 1.25, 1.5, 2].includes(chosen)) audio.playbackRate = chosen;
  });
})();
