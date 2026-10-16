/** The parts of the Home Assistant frontend objects the card uses. */

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

export interface HomeAssistant {
  states: Record<string, HassEntity | undefined>;
  entities?: Record<string, EntityRegistryDisplayEntry | undefined>;
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
  default_activity: string | null;
  activities: { id: string; name: string; icon: string | null }[];
  remote: {
    groups: Partial<Record<Group, GroupView>>;
    buttons: ButtonView[];
  } | null;
}
