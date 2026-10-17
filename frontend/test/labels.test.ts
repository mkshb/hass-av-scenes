/** Remote buttons get a readable label, never a translation key. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { commandLabel } from "../src/labels";
import { localize } from "../src/localize";

const de = (key: string) => localize("de", key);

test("known commands are translated", () => {
  assert.equal(commandLabel("guide", de), "EPG");
  assert.equal(commandLabel("volume_up", de), "Lauter");
});

test("own commands are made readable", () => {
  assert.equal(commandLabel("netflix", de), "Netflix");
  assert.equal(commandLabel("sleep_timer", de), "Sleep timer");
  assert.equal(commandLabel("1", de), "1");
});
