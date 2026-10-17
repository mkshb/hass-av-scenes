/** Card texts. The integration's own strings live in its translations. */

const STRINGS = {
  en: {
    "state.idle": "Off",
    "state.starting": "Starting …",
    "state.active": "On",
    "now.paused": "Paused",
    "state.stopping": "Stopping …",
    "state.error": "Error",
    power: "On/off",
    loading: "Loading …",
    not_found: "Room \"{room}\" not found",
    no_room: "Pick a room in the card settings",
    warnings: "Warnings",
    volume: "Volume",
    "command.volume_up": "Volume up",
    "command.volume_down": "Volume down",
    "command.mute": "Mute",
    "command.volume_set": "Volume slider",
    "command.select_source": "Select source",
    "command.channel_up": "Channel up",
    "command.channel_down": "Channel down",
    "command.play_pause": "Play/pause",
    "command.play": "Play",
    "command.pause": "Pause",
    "command.stop": "Stop",
    "command.next": "Next",
    "command.previous": "Previous",
    "command.up": "Up",
    "command.down": "Down",
    "command.left": "Left",
    "command.right": "Right",
    "command.ok": "OK",
    "command.back": "Back",
    "command.menu": "Menu",
    "command.home": "Home",
    "command.info": "Info",
    "command.guide": "Guide",
    "command.exit": "Exit",
    "editor.room": "Room",
    "editor.name": "Title (optional)",
  },
  de: {
    "state.idle": "Aus",
    "state.starting": "Startet …",
    "state.active": "An",
    "now.paused": "Pausiert",
    "state.stopping": "Stoppt …",
    "state.error": "Fehler",
    power: "Ein/Aus",
    loading: "Lädt …",
    not_found: "Raum „{room}“ nicht gefunden",
    no_room: "Bitte in den Karteneinstellungen einen Raum wählen",
    warnings: "Warnungen",
    volume: "Lautstärke",
    "command.volume_up": "Lauter",
    "command.volume_down": "Leiser",
    "command.mute": "Stumm",
    "command.volume_set": "Lautstärkeregler",
    "command.select_source": "Quelle wählen",
    "command.channel_up": "Kanal hoch",
    "command.channel_down": "Kanal runter",
    "command.play_pause": "Wiedergabe/Pause",
    "command.play": "Wiedergabe",
    "command.pause": "Pause",
    "command.stop": "Stopp",
    "command.next": "Weiter",
    "command.previous": "Zurück",
    "command.up": "Hoch",
    "command.down": "Runter",
    "command.left": "Links",
    "command.right": "Rechts",
    "command.ok": "OK",
    "command.back": "Zurück",
    "command.menu": "Menü",
    "command.home": "Start",
    "command.info": "Info",
    "command.guide": "EPG",
    "command.exit": "Beenden",
    "editor.room": "Raum",
    "editor.name": "Titel (optional)",
  },
} as const;

export type StringKey = keyof (typeof STRINGS)["en"];

export function localize(
  language: string | undefined,
  key: StringKey | string,
  params: Record<string, string> = {},
): string {
  const lang = (language ?? "en").split("-")[0];
  const table: Record<string, string> = lang in STRINGS
    ? STRINGS[lang as keyof typeof STRINGS]
    : STRINGS.en;
  let text = table[key] ?? (STRINGS.en as Record<string, string>)[key] ?? key;
  for (const [name, value] of Object.entries(params)) {
    text = text.replace(`{${name}}`, value);
  }
  return text;
}
