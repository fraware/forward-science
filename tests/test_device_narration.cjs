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

function createPage({ supported = true, saved = null, storageDisabled = false } = {}) {
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
    speechSynthesis: supported ? synth : undefined,
    SpeechSynthesisUtterance: supported ? function Utterance(text) { this.text = text; } : undefined,
    localStorage: {
      getItem: (key) => { if (storageDisabled) throw Error("storage blocked"); return storage.get(key) || null; },
      setItem: (key, value) => { if (storageDisabled) throw Error("storage blocked"); storage.set(key, value); },
      removeItem: (key) => { if (storageDisabled) throw Error("storage blocked"); storage.delete(key); },
    },
    addEventListener() {},
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
  return { panel, elements, synth, storage };
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
