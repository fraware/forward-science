/**
 * A local, non-persistent reading-position indicator for the six essays.
 * No reading history, audio player, accounts, tracking, or network requests.
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
})();
