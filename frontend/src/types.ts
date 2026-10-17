/** The parts of the Home Assistant frontend objects the card uses. */

import type { Cooling, Current } from "./progress";

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

/** Entity registry entry as the frontend has it (hass.entities). */
export interface EntityRegistryDisplayEntry {
  entity_id: string;
  device_id?: string | null;
  platform?: string;
}

/** Device registry entry as the frontend has it (hass.devices). */
export interface DeviceRegistryEntry {
  id: string;
  identifiers?: [string, string][];
}

export interface HomeAssistant {
  states: Record<string, HassEntity | undefined>;
  entities?: Record<string, EntityRegistryDisplayEntry | undefined>;
  devices?: Record<string, DeviceRegistryEntry | undefined>;
  language: string;
  connection: {
    subscribeMessage<T>(
      callback: (message: T) => void,
      message: Record<string, unknown>,
    ): Promise<() => Promise<void>>;
  };
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
  ): Promise<unknown>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
}

export interface CardConfig {
  type: string;
  room: string;
  entry_id?: string;
  name?: string;
}

/** av_scenes/control/rooms */
export interface RoomInfo {
  entry_id: string;
  room: string;
  name: string;
  area_id: string | null;
}

export type ActivityState = "idle" | "starting" | "active" | "stopping" | "error";

export type Group = "volume" | "channels" | "transport" | "navigation";

export interface GroupView {
  device: string | null;
  entity_id: string | null;
  commands: string[];
  /** Navigation only: a swipe area instead of the arrow keys */
  touchpad?: boolean;
}

export interface ButtonView {
  command: string;
  /** Quick select: the source (or app) for select_source */
  value: string | null;
  name: string | null;
  icon: string | null;
  device: string | null;
}

/** av_scenes/control/subscribe – sent now and on every change. */
export interface RoomView {
  entry_id: string;
  room: string;
  name: string;
  area_id: string | null;
  state: ActivityState;
  activity: string | null;
  error: string | null;
  warnings: string[];
  progress: [number, number];
  /** What a start or stop is busy with, see progress.ts */
  current: Current | null;
  /** Power switches cut after their devices cooled down, also while the room is off */
  cooling: Cooling[];
  default_activity: string | null;
  activities: { id: string; name: string; icon: string | null }[];
  remote: {
    groups: Partial<Record<Group, GroupView>>;
    buttons: ButtonView[];
    /** The media player whose title and artwork the card shows */
    media: string | null;
  } | null;
}
