/** What the card says a start or stop is busy with. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { localize } from "../src/localize";
import { progressText } from "../src/progress";

const NOW = Date.parse("2026-10-17T20:00:00Z");
const de = (key: string, params?: Record<string, string>) => localize("de", key, params);
const en = (key: string, params?: Record<string, string>) => localize("en", key, params);
const inSeconds = (s: number) => new Date(NOW + s * 1000).toISOString();

test("nothing to show", () => {
  assert.equal(progressText(null, NOW, de), undefined);
  assert.equal(progressText(undefined, NOW, de), undefined);
});

test("a device that boots, with the time left", () => {
  assert.deepEqual(progressText({ kind: "boot", name: "Beamer", until: inSeconds(41.2) }, NOW, de), {
    text: "Beamer bootet",
    time: "noch 42 s",
  });
  assert.deepEqual(progressText({ kind: "warm_up", name: "Onkyo", until: inSeconds(90) }, NOW, en), {
    text: "Onkyo is starting up",
    time: "1:30 left",
  });
});

test("waiting for a device: at most the timeout, never below zero", () => {
  assert.deepEqual(progressText({ kind: "ready", name: "Apple TV", until: inSeconds(-3) }, NOW, de), {
    text: "Warte auf Apple TV",
    time: "höchstens noch 0 s",
  });
});

test("switching, without a time", () => {
  assert.deepEqual(progressText({ kind: "turn_on", name: "VU+" }, NOW, de), { text: "VU+ wird eingeschaltet" });
  assert.deepEqual(progressText({ kind: "power_off", name: null }, NOW, en), { text: "Switching the outlets off" });
  assert.deepEqual(progressText({ kind: "reload", name: "Apple TV" }, NOW, de), {
    text: "Apple TV wird neu verbunden",
  });
});

test("steps and the wait after a step", () => {
  const step = { kind: "step", name: "Onkyo", step: 1, steps: 3, step_type: "set_source" };
  assert.deepEqual(progressText(step, NOW, de), { text: "Schritt 1 von 3: Quelle wählen (Onkyo)" });
  const action = { kind: "step", name: null, step: 2, steps: 3, step_type: "call_action" };
  assert.deepEqual(progressText(action, NOW, en), { text: "Step 2 of 3: Run action" });
  const wait = { kind: "wait", name: null, step: 3, steps: 3, until: inSeconds(2) };
  assert.deepEqual(progressText(wait, NOW, de), { text: "Schritt 3 von 3: warten", time: "noch 2 s" });
});

test("waiting for the actions on start and stop", () => {
  assert.equal(progressText({ kind: "hooks", name: null, hook: "on_start" }, NOW, de)?.text, "Warte auf die Aktionen beim Start");
  assert.equal(progressText({ kind: "hooks", name: null, hook: "on_stop" }, NOW, en)?.text, "Waiting for the actions on stop");
});
