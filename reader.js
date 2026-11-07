/**
 * A local, non-persistent reading-position indicator for the six essays.
 * No persistent reading history, accounts, analytics or unsolicited audio playback.
 */
(() => {
  "use strict";

  const article = document.querySelector('article[aria-label="Full essay"]');
  const indicator = document.querySelector(".reading-progress span");
  if (!article || !indicator) return;

  // Retire the former reading-history feature, including existing local state.
  try { window.localStorage.removeItem("forward-science:reading:v1"); }
  catch { /* Browsers may block storage; reading works independently. */ }

  let scheduled = false;
  const update = () => {
    scheduled = false;
    const top = article.getBoundingClientRect().top + window.scrollY;
    const bottom = article.getBoundingClientRect().bottom + window.scrollY;
    const position = window.scrollY + window.innerHeight * 0.38;
    const progress = Math.min(1, Math.max(0, (position - top) / Math.max(1, bottom - top)));
    indicator.style.width = (progress * 100).toFixed(1) + "%";
  };
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(update);
  };

  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  schedule();

  const disclosure = document.querySelector("details#listen.listen-option");
  const audio = disclosure?.querySelector("audio[data-essay-audio]");
  if (disclosure && audio) {
    // Opening is a user choice; loading metadata never starts playback.
    const openFromLink = () => {
      if (window.location.hash === "#listen") disclosure.open = true;
    };
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) {
        audio.preload = "metadata";
      } else if (!audio.paused) {
        audio.pause();
      }
    });
    window.addEventListener("hashchange", openFromLink);
    openFromLink();
  }
})();
