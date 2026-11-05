"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const scriptPath = path.join(__dirname, "..", "device-narration.js");
const source = fs.readFileSync(scriptPath, "utf8");
const { splitNarrationText } = require(scriptPath);

test("speech chunks reconstruct the exact normalized text", () => {
  for (const passage of [
    "A precise claim followed by another scientific sentence.",
    "An experiment; a measurement, and a defensible next action. ".repeat(24),
    "longword".repeat(90),
  ]) {
    const chunks = splitNarrationText(passage, 100);
    assert(chunks.every(Boolean));
    assert.equal(chunks.join(" ").replace(/\s+/g, " "),
      passage.trim().replace(/\s+/g, " "));
  }
  assert.deepEqual(splitNarrationText("  "), []);
  assert.throws(() => splitNarrationText("test", 12), RangeError);
});

function createPage({ supported = true, saved = null, storageDisabled = false, anchor = "" } = {}) {
  const elements = new Map();
  const el = (extra = {}) => Object.assign({
    textContent: "", value: "", disabled: false, hidden: false,
    events: new Map(), children: [], classList: { toggle() {} },
    addEventListener(name, callback) { this.events.set(name, callback); },
    click() { this.events.get("click")?.(); },
    change(value) { this.value = value; this.events.get("change")?.(); },
    replaceChildren() { this.children = []; },
    appendChild(child) { this.children.push(child); },
  }, extra);
  for (const key of ["play", "pause", "stop", "previous", "next", "rate", "voice", "status"]) {
    elements.set(key, el({ value: key === "rate" ? "1" : "" }));
  }
  const panel = el({ hidden: true, querySelector(query) {
    return elements.get(query.match(/data-speech-([\w-]+)/)[1]);
  } });
  const paragraphs = [
    el({ id: "p-01", textContent: "First paragraph with source-faithful language." }),
    el({ id: "p-02", textContent: "Second paragraph about scientific evidence." }),
    el({ id: "p-03", textContent: "A final paragraph and conclusion." }),
  ];
  const article = el({ querySelectorAll: () => paragraphs });
  const storageKey = "forward-science:device-narration:v1:scientific-loop";
  const storage = new Map(saved ? [[storageKey, JSON.stringify(saved)]] : []);
  const synth = {
    spoken: [], cancelled: 0,
    getVoices: () => [{ name: "Local test voice", lang: "en-US", voiceURI: "test:voice", localService: true }],
    speak(utterance) { this.spoken.push(utterance); },
    cancel() { this.cancelled++; },
    addEventListener() {},
  };
  const window = {
    location: { hash: anchor },
    speechSynthesis: supported ? synth : undefined,
    SpeechSynthesisUtterance: supported ? function Utterance(text) { this.text = text; } : undefined,
    localStorage: {
      getItem: (key) => { if (storageDisabled) throw Error("storage blocked"); return storage.get(key) || null; },
      setItem: (key, value) => { if (storageDisabled) throw Error("storage blocked"); storage.set(key, value); },
      removeItem: (key) => { if (storageDisabled) throw Error("storage blocked"); storage.delete(key); },
    },
    events: new Map(),
    addEventListener(name, callback) { this.events.set(name, callback); },
    dispatch(name) { this.events.get(name)?.(); },
  };
  const document = {
    body: { dataset: { essaySlug: "scientific-loop" } },
    querySelector(query) {
      if (query.includes("device-narration")) return panel;
      if (query.includes("Full essay")) return article;
      return null;
    },
    createElement: () => el(),
  };
  vm.runInNewContext(source, { window, document });
  return { panel, elements, synth, storage, window };
}

test("unsupported browsers receive no misleading listening controls", () => {
  assert.equal(createPage({ supported: false }).panel.hidden, true);
});

test("speech never autoplays; supports paragraph progression and pause", () => {
  const ui = createPage();
  assert.equal(ui.panel.hidden, false);
  assert.equal(ui.synth.spoken.length, 0);
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken[0].text, "First paragraph with source-faithful language.");
  ui.synth.spoken[0].onend();
  assert.equal(ui.synth.spoken[1].text, "Second paragraph about scientific evidence.");
  ui.elements.get("pause").click();
  assert.equal(ui.elements.get("play").textContent, "Resume");
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken[2].text, "Second paragraph about scientific evidence.");
  ui.elements.get("stop").click();
  assert.equal(ui.elements.get("stop").disabled, true);
  assert.equal(ui.storage.size, 0);
});

test("saved positions resume at a valid paragraph and clear on completion", () => {
  const ui = createPage({
    saved: { paragraph: 2, chunk: 0, rate: 1.25, voice: "test:voice" },
  });
  assert.equal(ui.elements.get("play").textContent, "Resume");
  assert.equal(ui.elements.get("rate").value, "1.25");
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken[0].text, "A final paragraph and conclusion.");
  ui.synth.spoken[0].onend();
  assert.match(ui.elements.get("status").textContent, /completed/);
  assert.equal(ui.storage.size, 0);
});

test("blocked local storage does not prevent playback", () => {
  const ui = createPage({ storageDisabled: true });
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken.length, 1);
  ui.elements.get("stop").click();
  assert.equal(ui.elements.get("play").disabled, false);
});


test("spontaneous browser interruption releases the Play control and keeps position", () => {
  for (const reason of ["interrupted", "canceled", "audio-busy"]) {
    const ui = createPage();
    ui.elements.get("play").click();
    const interruptedUtterance = ui.synth.spoken.at(-1);
    interruptedUtterance.onerror({ error: reason });
    assert.equal(ui.elements.get("play").disabled, false);
    assert.equal(ui.elements.get("play").textContent, "Resume");
    assert.equal(ui.elements.get("pause").disabled, true);
    assert.match(ui.elements.get("status").textContent, /Resume/);
    const saved = JSON.parse(ui.storage.get("forward-science:device-narration:v1:scientific-loop"));
    assert.equal(saved.paragraph, 0);
    assert.equal(saved.chunk, 0);
    ui.elements.get("play").click();
    assert.equal(ui.synth.spoken.length, 2);
  }
});

test("back-forward cache pagehide pauses speech and ignores stale completion", () => {
  const ui = createPage();
  ui.elements.get("play").click();
  const oldUtterance = ui.synth.spoken.at(-1);
  const cancellations = ui.synth.cancelled;
  ui.window.dispatch("pagehide");
  assert.equal(ui.synth.cancelled, cancellations + 1);
  assert.equal(ui.elements.get("play").textContent, "Resume");
  assert.equal(ui.elements.get("play").disabled, false);
  assert.equal(ui.elements.get("pause").disabled, true);
  assert.match(ui.elements.get("status").textContent, /Paused/);
  oldUtterance.onend();  // Late callback from a canceled utterance must be inert.
  assert.equal(ui.synth.spoken.length, 1);
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken.length, 2);
  assert.equal(ui.synth.spoken[1].text, oldUtterance.text);
});

test("pagehide leaves already paused and idle narration unchanged", () => {
  const idle = createPage();
  idle.window.dispatch("pagehide");
  assert.equal(idle.synth.cancelled, 0);
  assert.equal(idle.elements.get("play").textContent, "Play");

  const paused = createPage();
  paused.elements.get("play").click();
  paused.elements.get("pause").click();
  const cancelled = paused.synth.cancelled;
  paused.window.dispatch("pagehide");
  assert.equal(paused.synth.cancelled, cancelled);
  assert.equal(paused.elements.get("play").textContent, "Resume");
});


test("deep links take precedence over a saved narration position", () => {
  const ui = createPage({
    anchor: "#p-03",
    saved: { paragraph: 0, chunk: 0, rate: 1.5, voice: "test:voice" },
  });
  assert.equal(ui.elements.get("play").textContent, "Play");
  assert.equal(ui.elements.get("rate").value, "1.5");
  assert.match(ui.elements.get("status").textContent, /paragraph 3 of 3/);
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken.at(-1).text, "A final paragraph and conclusion.");
});

test("section navigation pauses and retargets speech without autoplay", () => {
  const ui = createPage();
  ui.elements.get("play").click();
  const firstUtterance = ui.synth.spoken[0];
  const countBefore = ui.synth.spoken.length;
  ui.window.location.hash = "#p-02";
  ui.window.dispatch("hashchange");
  assert.equal(ui.elements.get("play").textContent, "Resume");
  assert.equal(ui.synth.spoken.length, countBefore);
  firstUtterance.onend();
  assert.equal(ui.synth.spoken.length, countBefore);
  ui.elements.get("play").click();
  assert.equal(ui.synth.spoken.at(-1).text, "Second paragraph about scientific evidence.");
  ui.window.location.hash = "#irrelevant";
  ui.window.dispatch("hashchange");
  assert.equal(ui.elements.get("play").disabled, true);
});
