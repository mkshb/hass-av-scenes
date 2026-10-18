/** Device settings of the card as the panel edits them. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { autoSettings, cleanRemote, deviceAutoSettings, deviceList, type Room } from "../src/panel/model";
import type { HomeAssistant } from "../src/types";

const hass = {
  states: {
    "media_player.onkyo": {
      entity_id: "media_player.onkyo",
      state: "on",
      attributes: { source_list: ["SAT", "NET"], sound_mode_list: ["THX"] },
    },
    "media_player.vu": { entity_id: "media_player.vu", state: "off", attributes: {} },
  },
} as unknown as HomeAssistant;

const room: Room = {
  devices: {
    onkyo: { entity_id: "media_player.onkyo" },
    vu: { entity_id: "media_player.vu" },
    plug: { entity_id: "switch.plug" },
  },
  activities: { tv: { devices: ["onkyo", "vu", "plug"] } },
};

test("a list is live while the device has one, else remembered", () => {
  assert.deepEqual(deviceList(hass, {}, "media_player.onkyo", "sound_mode_list"), ["THX"]);
  assert.deepEqual(deviceList(hass, { "media_player.vu": ["ZDF"] }, "media_player.vu"), ["ZDF"]);
  assert.deepEqual(deviceList(hass, {}, undefined), []);
});

test("from the devices: every known list of the activity's media players", () => {
  const lists = { source_list: { "media_player.vu": ["ZDF"] }, sound_mode_list: {} };
  assert.deepEqual(autoSettings(hass, room, room.activities!.tv, lists), [
    { device: "onkyo", setting: "source" },
    { device: "onkyo", setting: "sound_mode" },
    { device: "vu", setting: "source" },
  ]);
});

test("no settings in the card stays an empty list, automatic has none", () => {
  assert.deepEqual(cleanRemote({ settings: [], buttons: [] }), { settings: [] });
  assert.deepEqual(cleanRemote({ buttons: [] }), {});
});

test("a device offers its related numbers and selects automatically", () => {
  const related = { "media_player.onkyo": ["number.onkyo_bass"], "switch.plug": ["select.plug_led"] };
  assert.deepEqual(deviceAutoSettings(hass, room, "onkyo", {}, related), [
    { device: "onkyo", setting: "source" },
    { device: "onkyo", setting: "sound_mode" },
    { device: "onkyo", entity: "number.onkyo_bass" },
  ]);
  // Not a media player: only its entities
  assert.deepEqual(deviceAutoSettings(hass, room, "plug", {}, related), [
    { device: "plug", entity: "select.plug_led" },
  ]);
});

test("a device's own choice replaces the automatic one, also when empty", () => {
  const chosen: Room = {
    ...room,
    devices: {
      ...room.devices,
      onkyo: { entity_id: "media_player.onkyo", settings: [{ entity: "number.onkyo_bass" }] },
      vu: { entity_id: "media_player.vu", settings: [] },
    },
  };
  const lists = { source_list: { "media_player.vu": ["ZDF"] }, sound_mode_list: {} };
  assert.deepEqual(autoSettings(hass, chosen, chosen.activities!.tv, lists), [
    { device: "onkyo", entity: "number.onkyo_bass" },
  ]);
});
