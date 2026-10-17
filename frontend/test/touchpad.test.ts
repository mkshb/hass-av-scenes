/** The swipe area turns movement into arrow keys and a tap into OK. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { STEP, Swipe, touchpadKey, useTouchpad } from "../src/touchpad";

test("a tap is OK", () => {
  const swipe = new Swipe();
  swipe.start(100, 100, 0);
  assert.deepEqual(swipe.move(103, 98), []);
  assert.equal(swipe.end(104, 101, 200), true);
});

test("a long press without moving is no tap", () => {
  const swipe = new Swipe();
  swipe.start(100, 100, 0);
  assert.equal(swipe.end(100, 100, 900), false);
});

test("one step per STEP pixels, in the direction that dominates", () => {
  const swipe = new Swipe();
  swipe.start(0, 0, 0);
  assert.deepEqual(swipe.move(STEP - 1, 5), []);
  assert.deepEqual(swipe.move(STEP + 2, 5), ["right"]);
  // A fast move covers several steps at once
  assert.deepEqual(swipe.move(STEP * 3 + 2, 5), ["right", "right"]);
  // Back to the left from where the steps ended
  assert.deepEqual(swipe.move(STEP * 2, 5), ["left"]);
  assert.equal(swipe.end(STEP * 2, 5, 300), false);
});

test("vertical: down on the screen is down", () => {
  const swipe = new Swipe();
  swipe.start(50, 50, 0);
  assert.deepEqual(swipe.move(55, 50 + STEP), ["down"]);
  assert.deepEqual(swipe.move(55, 50 - STEP), ["up", "up"]);
});

test("a diagonal turning sideways follows the new direction", () => {
  const swipe = new Swipe();
  swipe.start(0, 0, 0);
  assert.deepEqual(swipe.move(10, STEP), ["down"]);
  assert.deepEqual(swipe.move(10 + STEP, STEP + 5), ["right"]);
});

test("the viewer's choice wins over the activity's setting", () => {
  assert.equal(useTouchpad(null, true), true);
  assert.equal(useTouchpad(undefined, false), false);
  assert.equal(useTouchpad("off", true), false);
  assert.equal(useTouchpad("on", false), true);
  assert.equal(useTouchpad("garbage", true), true);
  assert.equal(touchpadKey("szb", "atv"), "av-scenes-touchpad:szb:atv");
});
