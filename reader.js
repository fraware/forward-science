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
  const title = document.querySelector(".chapter-heading h1")?.textContent?.trim() || "essay";
  const prior = readState();
  if (prior?.slug === slug && prior.paragraph && document.getElementById(prior.paragraph)) {
    resume.hidden = false;
    resume.addEventListener("click", () => {
      readingStarted = true;
      document.getElementById(prior.paragraph)?.scrollIntoView({ behavior: "smooth", block: "start" });
      resume.hidden = true;
      // The ensuing scroll events track the new position. An eager update
      // here would record the heading viewport before scrolling completes.
    });
  }

  // Initial rendering may intersect the first paragraph on tall monitors.
  // Do not erase an existing bookmark before an intentional reading action.
  let readingStarted = window.scrollY > 0 ||
    (/^#p-\d{2,3}$/.test(window.location.hash) &&
      Boolean(document.getElementById(window.location.hash.slice(1))));
  let lastParagraph = "";
  let ticking = false;
  const update = () => {
    ticking = false;
    const top = article.getBoundingClientRect().top + window.scrollY;
    const bottom = article.getBoundingClientRect().bottom + window.scrollY;
    const position = window.scrollY + window.innerHeight * 0.38;
    const fraction = Math.min(1, Math.max(0, (position - top) / Math.max(1, bottom - top)));
    if (track) track.style.width = (fraction * 100).toFixed(1) + "%";
    if (!readingStarted || position < top || paragraphs.length === 0) return;
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
  window.addEventListener("scroll", () => {
    readingStarted = true;
    schedule();
  }, { passive: true });
  window.addEventListener("resize", schedule);
  schedule();

  // The media player appears for source-pinned public previews or approved MP3s.
  // Resume markers are bound to the *recording*, never merely to its essay:
  // a remastered/replaced recording must not inherit obsolete seek positions.
  const audio = document.querySelector("audio[data-audio-for]");
  if (!audio) return;

  const disclosure = document.querySelector("details#listen.audio-edition");
  if (disclosure) {
    // Direct links from the series index are an explicit listening choice.
    // Open the player without starting playback.
    const openLinkedAudio = () => {
      if (window.location.hash === "#listen") disclosure.open = true;
    };
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) {
        // Avoid any MP3 request on an ordinary reading-only page visit.
        audio.preload = "metadata";
        audio.load();
      } else if (!audio.paused) {
        // Closing the player must not leave invisible audio playing.
        audio.pause();
      }
    });
    window.addEventListener("hashchange", openLinkedAudio);
    openLinkedAudio();
  }

  const audioHash = audio.dataset.audioSha;
  const rateKey = "forward-science:audio-rate:v1";
  const speed = document.querySelector(".audio-speed");
  const rewind = document.querySelector(".audio-skip-back");
  const forward = document.querySelector(".audio-skip-forward");
  const resumeAudio = document.querySelector(".audio-resume");
  const feedback = document.querySelector(".audio-feedback");
  const feedbackText = (message) => { if (feedback) feedback.textContent = message; };

  // A missing/invalid version identifier means there is no safe resume state.
  const hasVerifiedVersion = /^[a-f0-9]{64}$/.test(audioHash || "");
  const savedAudio = (() => {
    if (!hasVerifiedVersion) return null;
    try {
      const raw = localStorage.getItem(audioKey(slug));
      const position = raw ? JSON.parse(raw) : null;
      return position && position.sha256 === audioHash
        && Number.isFinite(position.time) && position.time >= 0 ? position : null;
    } catch { return null; }
  })();
  const savedRate = (() => {
    try { return Number(localStorage.getItem(rateKey)); }
    catch { return NaN; }
  })();
  const speeds = [0.75, 1, 1.25, 1.5, 2];
  if (speed && speeds.includes(savedRate)) speed.value = String(savedRate);
  if (speed) audio.playbackRate = Number(speed.value) || 1;

  const validDuration = () => Number.isFinite(audio.duration) && audio.duration > 0;
  const seekTo = (seconds) => {
    if (!validDuration() || !Number.isFinite(seconds)) return false;
    audio.currentTime = Math.max(0, Math.min(audio.duration, seconds));
    return true;
  };
  const formatTime = (seconds) => {
    const whole = Math.max(0, Math.floor(seconds));
    return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
  };
  // Loading a recording or leaving an untouched page must never erase an
  // existing listening bookmark. Browsers may dispatch timeupdate/pause
  // during media initialization, even before a visitor presses Play.
  let sessionActive = false;
  let lastSavedBucket = -1;
  const storePosition = () => {
    if (!sessionActive || !hasVerifiedVersion
        || !Number.isFinite(audio.currentTime) || !validDuration()) return;
    store(audioKey(slug), {
      sha256: audioHash,
      time: Math.max(0, Math.min(audio.duration, audio.currentTime)),
    });
  };

  // Throttle playback writes but record exact position on pause/navigation.
  audio.addEventListener("timeupdate", () => {
    if (!sessionActive || !Number.isFinite(audio.currentTime)) return;
    const bucket = Math.floor(audio.currentTime / 5);
    if (bucket !== lastSavedBucket) {
      lastSavedBucket = bucket;
      storePosition();
    }
  });
  // Scrubbing with native controls is a listening action even while paused.
  audio.addEventListener("seeked", () => {
    sessionActive = true;
    lastSavedBucket = -1;
    storePosition();
  });
  audio.addEventListener("pause", storePosition);
  window.addEventListener("pagehide", storePosition);
  audio.addEventListener("ended", () => {
    sessionActive = false;
    lastSavedBucket = -1;
    if (hasVerifiedVersion) {
      store(audioKey(slug), { sha256: audioHash, time: 0 });
    }
    if (resumeAudio) resumeAudio.hidden = true;
  });
  audio.addEventListener("play", () => {
    sessionActive = true;
    if (resumeAudio) resumeAudio.hidden = true;
    feedbackText("");
  });

  const beginPlayback = () => {
    try {
      const attempt = audio.play();
      if (attempt && typeof attempt.catch === "function") {
        attempt.catch(() => feedbackText("Use the audio player's Play button to begin."));
      }
    } catch {
      feedbackText("Use the audio player's Play button to begin.");
    }
  };

  audio.addEventListener("loadedmetadata", () => {
    const ready = validDuration();
    if (rewind) rewind.disabled = !ready;
    if (forward) forward.disabled = !ready;
    if (resumeAudio) {
      const resumable = ready && savedAudio && savedAudio.time > 12
        && savedAudio.time < audio.duration - 12;
      resumeAudio.hidden = !resumable;
      if (resumable) resumeAudio.textContent = "Resume at " + formatTime(savedAudio.time);
    }
  }, { once: true });
  audio.addEventListener("error", () => {
    if (rewind) rewind.disabled = true;
    if (forward) forward.disabled = true;
    if (resumeAudio) resumeAudio.hidden = true;
    feedbackText("This recording is unavailable. Try reloading the page.");
  });

  rewind?.addEventListener("click", () => {
    if (seekTo(audio.currentTime - 15)) {
      sessionActive = true;
      storePosition();
    }
  });
  forward?.addEventListener("click", () => {
    if (seekTo(audio.currentTime + 30)) {
      sessionActive = true;
      storePosition();
    }
  });
  resumeAudio?.addEventListener("click", () => {
    if (savedAudio && seekTo(savedAudio.time)) {
      sessionActive = true;
      resumeAudio.hidden = true;
      storePosition();
      beginPlayback(); // Initiated by an explicit user interaction.
    }
  });
  speed?.addEventListener("change", () => {
    const chosen = Number(speed.value);
    if (!speeds.includes(chosen)) return;
    audio.playbackRate = chosen;
    try { localStorage.setItem(rateKey, String(chosen)); }
    catch { /* Browser-local preferences are optional. */ }
  });

  // Optional mobile lock-screen and headphone metadata; native controls remain
  // the accessible source of truth, including on browsers without Media Session.
  if (typeof navigator !== "undefined" && navigator.mediaSession
      && typeof window.MediaMetadata === "function") {
    try {
      navigator.mediaSession.metadata = new window.MediaMetadata({
        title,
        artist: "Mateo H. Petel",
        album: "Forward Science",
      });
      const actions = {
        seekbackward: (details) => {
          if (seekTo(audio.currentTime - (details?.seekOffset || 15))) {
            sessionActive = true;
            storePosition();
          }
        },
        seekforward: (details) => {
          if (seekTo(audio.currentTime + (details?.seekOffset || 30))) {
            sessionActive = true;
            storePosition();
          }
        },
      };
      for (const [action, callback] of Object.entries(actions)) {
        try { navigator.mediaSession.setActionHandler(action, callback); }
        catch { /* Unsupported action on this browser. */ }
      }
    } catch { /* Media Session support is optional. */ }
  }
})();
