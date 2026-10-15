/**
 * Configuration model of the panel: the stored YAML structure, edited as
 * plain objects. Validation stays in the integration (config/validate).
 */
import type { HomeAssistant } from "../types";

export type Obj = Record<string, unknown>;

export interface Device extends Obj {
  entity_id: string;
  name?: string;
  power_switch?: string | null;
  ready?: { timeout?: number; reload_integration?: boolean; on_timeout?: string } | null;
  delay_after_power?: number;
  delay_after_on?: number;
  delay_after_off?: number;
  commands?: Obj;
}

export interface Step extends Obj {
  type: string;
  device?: string;
}

export interface Activity extends Obj {
  name?: string;
  icon?: string;
  order?: number;
  devices?: string[];
  steps?: Step[];
  on_start?: unknown[];
  on_stop?: unknown[];
  remote?: Obj;
  commands?: Obj;
}

export interface Room extends Obj {
  name?: string;
  area_id?: string | null;
  devices?: Record<string, Device>;
  activities?: Record<string, Activity>;
}

export type Rooms = Record<string, Room>;

export const STEP_TYPES = [
  "power_on",
  "power_off",
  "set_source",
  "set_volume",
  "set_sound_mode",
  "set_brightness",
  "set_color_temp",
  "set_position",
  "set_tilt",
  "call_action",
  "delay",
  "wait_available",
] as const;

export const GROUPS = ["volume", "channels", "transport", "navigation"] as const;

const SECONDS = { number: { min: 0, max: 3600, step: 1, mode: "box", unit_of_measurement: "s" } };
const PERCENT = { number: { min: 0, max: 100, step: 1, mode: "slider" } };

/** ha-form schema of a step, depending on its type. */
export function stepSchema(
  hass: HomeAssistant,
  room: Room,
  step: Step,
  label: (key: string) => string,
): Obj[] {
  const devices = Object.entries(room.devices ?? {}).map(([id, d]) => ({
    value: id,
    label: d.name ? `${d.name} (${id})` : id,
  }));
  const deviceField = { name: "device", required: true, selector: { select: { options: devices, mode: "dropdown" } } };
  const entity = step.device ? room.devices?.[step.device]?.entity_id : undefined;
  const attrList = (attr: string): string[] => {
    const value = entity ? hass.states[entity]?.attributes[attr] : undefined;
    return Array.isArray(value) ? value.map(String) : [];
  };
  const fields: Record<string, Obj[]> = {
    power_on: [deviceField],
    power_off: [deviceField],
    set_source: [
      deviceField,
      { name: "source", required: true, selector: { select: { options: attrList("source_list"), custom_value: true, mode: "dropdown" } } },
    ],
    set_volume: [
      deviceField,
      { name: "volume_level", required: true, selector: { number: { min: 0, max: 1, step: 0.01, mode: "slider" } } },
    ],
    set_sound_mode: [
      deviceField,
      { name: "sound_mode", required: true, selector: { select: { options: attrList("sound_mode_list"), custom_value: true, mode: "dropdown" } } },
    ],
    set_brightness: [
      deviceField,
      { name: "brightness_pct", selector: PERCENT },
      { name: "color_temp_kelvin", selector: { color_temp: { unit: "kelvin", min: 2000, max: 6500 } } },
      { name: "transition", selector: SECONDS },
    ],
    set_color_temp: [
      deviceField,
      { name: "color_temp_kelvin", required: true, selector: { color_temp: { unit: "kelvin", min: 2000, max: 6500 } } },
    ],
    set_position: [deviceField, { name: "position", required: true, selector: PERCENT }],
    set_tilt: [deviceField, { name: "tilt_position", required: true, selector: PERCENT }],
    call_action: [
      { name: "action", required: true, selector: { text: {} } },
      { name: "target", selector: { target: {} } },
      { name: "data", selector: { object: {} } },
    ],
    delay: [],
    wait_available: [
      { ...deviceField, required: false },
      { name: "entity_id", selector: { entity: {} } },
      { name: "timeout", selector: SECONDS },
      { name: "reload_integration", selector: { boolean: {} } },
      {
        name: "on_timeout",
        selector: {
          select: {
            options: [
              { value: "abort", label: label("on_timeout_abort") },
              { value: "continue", label: label("on_timeout_continue") },
            ],
            mode: "dropdown",
          },
        },
      },
    ],
  };
  return [...(fields[step.type] ?? []), { name: "delay_after", selector: SECONDS }];
}

/** Drop empty optional values so the stored YAML stays tidy. */
export function clean<T extends Obj>(value: T, keep: string[] = []): T {
  const out: Obj = {};
  for (const [key, v] of Object.entries(value)) {
    if (keep.includes(key)) {
      out[key] = v;
    } else if (v === undefined || v === null || v === "") {
      continue;
    } else if (Array.isArray(v) && v.length === 0) {
      continue;
    } else if (typeof v === "object" && !Array.isArray(v) && Object.keys(v as Obj).length === 0) {
      continue;
    } else {
      out[key] = v;
    }
  }
  return out as T;
}

/** Home Assistant's slugify: lower case, no accents, underscores. */
export function slugify(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/ß/g, "ss")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function uniqueKey(base: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  const root = base || "item";
  if (!used.has(root)) {
    return root;
  }
  let n = 2;
  while (used.has(`${root}_${n}`)) {
    n += 1;
  }
  return `${root}_${n}`;
}

/** Where a device is referenced: activity names. */
export function deviceUsage(room: Room, deviceId: string): string[] {
  const where: string[] = [];
  for (const [id, activity] of Object.entries(room.activities ?? {})) {
    const used =
      (activity.devices ?? []).includes(deviceId) ||
      (activity.steps ?? []).some((s) => s.device === deviceId) ||
      GROUPS.some((g) => activity.remote?.[g] === deviceId) ||
      ((activity.remote?.buttons as Obj[] | undefined) ?? []).some(
        (b) => typeof b === "object" && b?.device === deviceId,
      );
    if (used) {
      where.push(activity.name ?? id);
    }
  }
  return where;
}

/** Rename a device and every reference to it. */
export function renameDevice(room: Room, from: string, to: string): Room {
  const devices: Record<string, Device> = {};
  for (const [id, device] of Object.entries(room.devices ?? {})) {
    devices[id === from ? to : id] = device;
  }
  const swap = (v: unknown) => (v === from ? to : v);
  const activities: Record<string, Activity> = {};
  for (const [id, a] of Object.entries(room.activities ?? {})) {
    const remote = a.remote ? { ...a.remote } : undefined;
    if (remote) {
      for (const g of GROUPS) {
        if (g in remote) remote[g] = swap(remote[g]);
      }
      if (Array.isArray(remote.buttons)) {
        remote.buttons = remote.buttons.map((b) =>
          typeof b === "object" && b ? { ...(b as Obj), device: swap((b as Obj).device) } : b,
        );
      }
    }
    activities[id] = clean({
      ...a,
      devices: a.devices?.map((d) => swap(d) as string),
      steps: a.steps?.map((s) => (s.device === from ? { ...s, device: to } : s)),
      remote,
    });
  }
  return { ...room, devices, activities };
}
