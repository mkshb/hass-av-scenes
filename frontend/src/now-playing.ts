/** What a media player plays, as the card shows it above the remote. */
import type { HassEntity } from "./types";

/** States in which there is nothing to show as playing. */
const NOT_PLAYING = new Set(["off", "standby", "unavailable", "unknown"]);

export interface NowPlaying {
  title: string;
  /** The app, when the title is something else (e.g. "UHF" above "Tagesschau") */
  app?: string;
  /** Series with season and episode, else artist or album */
  subtitle?: string;
  picture?: string;
  playing: boolean;
  /** Seconds; only with a known length */
  duration?: number;
  /** Seconds, moved on since the player last reported it while playing */
  position?: number;
}

export function nowPlaying(state: HassEntity | undefined, now: number): NowPlaying | undefined {
  if (!state || NOT_PLAYING.has(state.state)) {
    return undefined;
  }
  const a = state.attributes;
  const text = (key: string) => (typeof a[key] === "string" && a[key] ? (a[key] as string) : undefined);
  const number = (key: string) => (typeof a[key] === "number" ? (a[key] as number) : undefined);
  const app = text("app_name");
  const title = text("media_title") ?? app;
  if (!title) {
    return undefined;
  }
  const season = number("media_season") ?? text("media_season");
  const episode = number("media_episode") ?? text("media_episode");
  const series = text("media_series_title");
  const subtitle =
    series && (season !== undefined || episode !== undefined)
      ? `${series} · ${[season !== undefined ? `S${season}` : "", episode !== undefined ? `E${episode}` : ""].filter(Boolean).join(" ")}`
      : (series ?? text("media_artist") ?? text("media_album_name"));
  const playing = state.state === "playing";
  const length = number("media_duration");
  const duration = length !== undefined && length > 0 ? length : undefined;
  let position = number("media_position");
  const updated = text("media_position_updated_at");
  if (position !== undefined && playing && updated && !Number.isNaN(Date.parse(updated))) {
    position += (now - Date.parse(updated)) / 1000;
  }
  if (position !== undefined && duration !== undefined) {
    position = Math.max(0, Math.min(duration, position));
  }
  return {
    title,
    app: title === app ? undefined : app,
    subtitle,
    picture: text("entity_picture"),
    playing,
    duration,
    position: duration !== undefined ? position : undefined,
  };
}

/** 75 -> "1:15", 3725 -> "1:02:05" */
export function clock(seconds: number): string {
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
