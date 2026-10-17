/** What the card shows as playing, from a media player's state. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { clock, nowPlaying } from "../src/now-playing";

const NOW = Date.parse("2026-10-17T20:00:00Z");

function player(state: string, attributes: Record<string, unknown>) {
  return { entity_id: "media_player.atv", state, attributes };
}

test("nothing while off, unavailable or without a title", () => {
  for (const state of ["off", "standby", "unavailable", "unknown"]) {
    assert.equal(nowPlaying(player(state, { media_title: "Tagesschau" }), NOW), undefined);
  }
  assert.equal(nowPlaying(player("idle", {}), NOW), undefined);
  assert.equal(nowPlaying(undefined, NOW), undefined);
});

test("an app with a live channel: app above the title, no progress", () => {
  const now = nowPlaying(
    player("playing", { app_name: "UHF", media_title: "Das Erste HD", entity_picture: "/api/pic" }),
    NOW,
  );
  assert.deepEqual(now, {
    title: "Das Erste HD",
    app: "UHF",
    subtitle: undefined,
    picture: "/api/pic",
    playing: true,
    duration: undefined,
    position: undefined,
  });
});

test("only an app: the app is the title", () => {
  const now = nowPlaying(player("idle", { app_name: "Netflix" }), NOW);
  assert.equal(now?.title, "Netflix");
  assert.equal(now?.app, undefined);
});

test("a series episode with progress moving on while it plays", () => {
  const now = nowPlaying(
    player("playing", {
      app_name: "Netflix",
      media_title: "Der Anfang",
      media_series_title: "Dark",
      media_season: 1,
      media_episode: 3,
      media_duration: 3000,
      media_position: 600,
      media_position_updated_at: "2026-10-17T19:59:30Z",
    }),
    NOW,
  );
  assert.equal(now?.subtitle, "Dark · S1 E3");
  assert.equal(now?.position, 630);
  assert.equal(now?.duration, 3000);
});

test("paused: the position stays, and never past the end", () => {
  const paused = nowPlaying(
    player("paused", {
      media_title: "Film",
      media_duration: 100,
      media_position: 40,
      media_position_updated_at: "2026-10-17T19:00:00Z",
    }),
    NOW,
  );
  assert.equal(paused?.playing, false);
  assert.equal(paused?.position, 40);
  const over = nowPlaying(
    player("playing", {
      media_title: "Film",
      media_duration: 100,
      media_position: 90,
      media_position_updated_at: "2026-10-17T19:00:00Z",
    }),
    NOW,
  );
  assert.equal(over?.position, 100);
});

test("music: artist below the title", () => {
  const now = nowPlaying(player("playing", { media_title: "Song", media_artist: "Band" }), NOW);
  assert.equal(now?.subtitle, "Band");
});

test("clock", () => {
  assert.equal(clock(0), "0:00");
  assert.equal(clock(75.9), "1:15");
  assert.equal(clock(3725), "1:02:05");
});
