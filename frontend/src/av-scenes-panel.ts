/**
 * AV Scenes configuration panel (admins only).
 *
 * Reads the configuration with av_scenes/config/get, checks it with
 * config/validate and saves it with config/save; the integration applies it
 * like a save in the options flow.
 */
import { LitElement, css, html, nothing, type TemplateResult } from "lit";

import "./panel/room-editor";
import { clean, slugify, uniqueKey, type Room, type Rooms, type Sources } from "./panel/model";
import { t } from "./panel/strings";
import type { HomeAssistant } from "./types";

interface Missing {
  room: string;
  path: string;
  entity_id: string;
}

interface Check {
  error: { path: string[]; message: string } | null;
  missing: Missing[];
}

type Banner =
  | { kind: "invalid"; path: string; message: string }
  | { kind: "missing"; missing: Missing[] }
  | { kind: "conflict" }
  | { kind: "saved" };

/** ha-form and its selectors are loaded lazily by HA; make sure they exist. */
async function loadHaElements(): Promise<void> {
  if (customElements.get("ha-form") && customElements.get("ha-selector")) {
    return;
  }
  const helpers = await (window as unknown as { loadCardHelpers: () => Promise<any> }).loadCardHelpers();
  const card = await helpers.createCardElement({ type: "entities", entities: [] });
  await card.constructor.getConfigElement();
  await customElements.whenDefined("ha-form");
}

export class AvScenesPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    _rooms: { state: true },
    _selected: { state: true },
    _loadError: { state: true },
    _banner: { state: true },
    _saving: { state: true },
    _ready: { state: true },
    _sources: { state: true },
  };

  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare _rooms?: Rooms;
  declare _selected?: string;
  declare _loadError?: string;
  declare _banner?: Banner;
  declare _saving: boolean;
  declare _ready: boolean;
  declare _sources: Sources;

  private _entryId?: string;
  private _revision?: string;
  private _original = "";
  private _loading = false;

  constructor() {
    super();
    this._saving = false;
    this._ready = false;
    this._sources = {};
  }

  private _t(key: string, params?: Record<string, string>): string {
    return t(this.hass?.language, key, params);
  }

  protected updated(): void {
    if (this.hass && !this._rooms && !this._loading && !this._loadError) {
      void this._load();
    }
  }

  private async _load(): Promise<void> {
    this._loading = true;
    try {
      await loadHaElements();
      this._ready = true;
      const result = await this.hass.callWS<{ entry_id: string; rooms: Rooms; revision: string }>({
        type: "av_scenes/config/get",
      });
      this._entryId = result.entry_id;
      this._revision = result.revision;
      this._original = JSON.stringify(result.rooms);
      this._rooms = result.rooms;
      this._banner = undefined;
      if (!this._selected || !(this._selected in result.rooms)) {
        this._selected = Object.keys(result.rooms)[0];
      }
      // Remembered source lists for the pickers; the panel works without them
      this._sources = await this.hass
        .callWS<Sources>({ type: "av_scenes/config/sources" })
        .catch(() => ({}));
    } catch (err) {
      this._loadError = (err as { message?: string })?.message ?? String(err);
    } finally {
      this._loading = false;
    }
  }

  private get _dirty(): boolean {
    return this._rooms !== undefined && JSON.stringify(this._rooms) !== this._original;
  }

  // ------------------------------------------------------------------
  // Editing
  // ------------------------------------------------------------------

  private _roomChanged(id: string, room: Room): void {
    this._rooms = { ...this._rooms, [id]: room };
    if (this._banner?.kind !== "conflict") {
      this._banner = undefined;
    }
  }

  private _addRoom(): void {
    const name = window.prompt(this._t("room_name"));
    if (!name?.trim()) {
      return;
    }
    const id = uniqueKey(slugify(name), Object.keys(this._rooms ?? {}));
    this._rooms = { ...this._rooms, [id]: { name: name.trim(), devices: {}, activities: {} } };
    this._selected = id;
  }

  private _deleteRoom(id: string): void {
    const room = this._rooms?.[id];
    if (!room || !window.confirm(this._t("delete_room_confirm", { name: room.name ?? id }))) {
      return;
    }
    const rooms = { ...this._rooms };
    delete rooms[id];
    this._rooms = rooms;
    this._selected = Object.keys(rooms)[0];
  }

  private _discard(): void {
    this._rooms = JSON.parse(this._original) as Rooms;
    this._banner = undefined;
  }

  private async _save(force = false): Promise<void> {
    if (!this._rooms || !this._revision) {
      return;
    }
    const rooms: Rooms = {};
    for (const [id, room] of Object.entries(this._rooms)) {
      rooms[id] = clean(room);
    }
    this._saving = true;
    try {
      const check = await this.hass.callWS<Check>({
        type: "av_scenes/config/validate",
        rooms,
        ...(this._selected ? { room: this._selected } : {}),
      });
      if (check.error) {
        this._banner = {
          kind: "invalid",
          path: check.error.path.join("."),
          message: check.error.message,
        };
        return;
      }
      if (check.missing.length && !force) {
        this._banner = { kind: "missing", missing: check.missing };
        return;
      }
      const result = await this.hass.callWS<{ revision: string }>({
        type: "av_scenes/config/save",
        rooms,
        revision: this._revision,
        entry_id: this._entryId,
      });
      this._revision = result.revision;
      this._original = JSON.stringify(rooms);
      this._rooms = rooms;
      this._banner = { kind: "saved" };
    } catch (err) {
      const error = err as { code?: string; message?: string };
      this._banner =
        error.code === "conflict"
          ? { kind: "conflict" }
          : { kind: "invalid", path: "", message: error.message ?? String(err) };
    } finally {
      this._saving = false;
    }
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------

  protected render(): TemplateResult {
    return html`
      <div class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <div class="main-title">${this._t("title")}</div>
        ${this._dirty ? html`<span class="dirty">${this._t("unsaved")}</span>` : nothing}
        <button class="flat" ?disabled=${!this._dirty || this._saving} @click=${this._discard}>
          ${this._t("discard")}
        </button>
        <button class="primary" ?disabled=${!this._dirty || this._saving} @click=${() => this._save()}>
          ${this._saving ? this._t("saving") : this._t("save")}
        </button>
      </div>
      <div class="content">${this._renderContent()}</div>
    `;
  }

  private _renderContent(): TemplateResult {
    if (this._loadError) {
      return html`<div class="banner error">${this._t("load_error", { error: this._loadError })}</div>`;
    }
    if (!this._rooms || !this._ready) {
      return html`<div class="empty">${this._t("loading")}</div>`;
    }
    const rooms = Object.entries(this._rooms);
    const selected = this._selected && this._rooms[this._selected] ? this._selected : undefined;
    return html`<div class="layout ${this.narrow ? "narrow" : ""}">
      <nav>
        <div class="nav-title">${this._t("rooms")}</div>
        ${rooms.map(
          ([id, room]) => html`<button
            class="room ${id === selected ? "active" : ""}"
            @click=${() => (this._selected = id)}
          >
            ${room.name ?? id}
          </button>`,
        )}
        <button class="room add" @click=${this._addRoom}>+ ${this._t("add_room")}</button>
      </nav>
      <main>
        ${this._renderBanner()}
        ${selected
          ? html`<av-scenes-room-editor
                .hass=${this.hass}
                .room=${this._rooms[selected]}
                .roomId=${selected}
                .sources=${this._sources}
                @room-changed=${(ev: CustomEvent<{ room: Room }>) => this._roomChanged(selected, ev.detail.room)}
              ></av-scenes-room-editor>
              <button class="delete-room" @click=${() => this._deleteRoom(selected)}>
                ${this._t("delete_room")}
              </button>`
          : html`<div class="empty">${this._t("no_rooms")}</div>`}
      </main>
    </div>`;
  }

  private _renderBanner(): TemplateResult | typeof nothing {
    const banner = this._banner;
    if (!banner) {
      return nothing;
    }
    switch (banner.kind) {
      case "saved":
        return html`<div class="banner ok">${this._t("saved")}</div>`;
      case "invalid":
        return html`<div class="banner error">
          ${this._t("invalid", { path: banner.path || "–", message: banner.message })}
        </div>`;
      case "conflict":
        return html`<div class="banner error">
          ${this._t("conflict")}
          <button class="flat" @click=${() => this._load()}>${this._t("reload")}</button>
        </div>`;
      case "missing":
        return html`<div class="banner warning">
          ${this._t("missing")}
          <ul>
            ${banner.missing.map((m) => html`<li><code>${m.entity_id}</code> (${m.path})</li>`)}
          </ul>
          <div class="sub">${this._t("missing_hint")}</div>
          <button class="primary" @click=${() => this._save(true)}>${this._t("save_anyway")}</button>
        </div>`;
    }
  }

  static styles = css`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      height: var(--header-height, 56px);
      padding: 0 12px;
      background: var(--app-header-background-color, var(--primary-color));
      color: var(--app-header-text-color, var(--text-primary-color, #fff));
      border-bottom: var(--app-header-border-bottom, none);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .main-title {
      flex: 1;
      font-size: 20px;
      margin-left: 4px;
    }
    .dirty {
      font-size: 0.85em;
      opacity: 0.85;
    }
    button {
      font: inherit;
      cursor: pointer;
    }
    button.primary,
    button.flat {
      border: none;
      border-radius: 18px;
      padding: 8px 16px;
    }
    button.primary {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .toolbar button.primary {
      background: var(--text-primary-color, #fff);
      color: var(--primary-color);
    }
    button.flat {
      background: none;
      color: inherit;
    }
    button:disabled {
      opacity: 0.4;
      cursor: default;
    }
    .content {
      padding: 16px;
      max-width: 1100px;
      margin: 0 auto;
      box-sizing: border-box;
    }
    .layout {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 24px;
    }
    .layout.narrow {
      grid-template-columns: 1fr;
    }
    nav {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .layout.narrow nav {
      flex-direction: row;
      flex-wrap: wrap;
    }
    .nav-title {
      font-weight: 500;
      color: var(--secondary-text-color);
      margin-bottom: 4px;
      width: 100%;
    }
    button.room {
      text-align: left;
      border: none;
      border-radius: 18px;
      padding: 8px 14px;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    button.room.active {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    button.room.add {
      background: none;
      color: var(--primary-color);
    }
    main {
      min-width: 0;
    }
    .banner {
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 16px;
      overflow-wrap: anywhere;
    }
    .banner.error {
      background: var(--error-color, #db4437);
      color: var(--text-primary-color, #fff);
    }
    .banner.warning {
      background: var(--warning-color, #ffa600);
      color: var(--text-primary-color, #fff);
    }
    .banner.ok {
      background: var(--success-color, #43a047);
      color: var(--text-primary-color, #fff);
    }
    .banner ul {
      margin: 8px 0;
    }
    .banner .sub {
      margin-bottom: 8px;
      opacity: 0.9;
    }
    .banner button.primary {
      background: var(--text-primary-color, #fff);
      color: var(--primary-text-color);
    }
    .banner button.flat {
      text-decoration: underline;
    }
    .empty {
      color: var(--secondary-text-color);
      padding: 24px 0;
    }
    button.delete-room {
      margin-top: 32px;
      background: none;
      border: none;
      color: var(--error-color, #db4437);
    }
  `;
}

if (!customElements.get("av-scenes-panel")) {
  customElements.define("av-scenes-panel", AvScenesPanel);
}
