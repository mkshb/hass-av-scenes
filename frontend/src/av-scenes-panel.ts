/**
 * AV Scenes configuration panel (admins only).
 *
 * Reads the configuration with av_scenes/config/get, checks it with
 * config/validate and saves it with config/save; the integration applies it
 * like a save in the options flow.
 */
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";

import "./panel/guide";
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
    _adding: { state: true },
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
  declare _adding: boolean;

  private _entryId?: string;
  private _revision?: string;
  private _original = "";
  private _loading = false;

  constructor() {
    super();
    this._saving = false;
    this._ready = false;
    this._sources = {};
    this._adding = false;
  }

  private _t(key: string, params?: Record<string, string>): string {
    return t(this.hass?.language, key, params);
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

  private _addRoom(name: string): void {
    this._adding = false;
    if (!name.trim()) {
      return;
    }
    const id = uniqueKey(slugify(name), Object.keys(this._rooms ?? {}));
    this._rooms = { ...this._rooms, [id]: { name: name.trim(), devices: {}, activities: {} } };
    this._selected = id;
  }

  private _renderAddRoom(): TemplateResult {
    if (!this._adding) {
      return html`<button class="room add" @click=${() => (this._adding = true)}>+ ${this._t("add_room")}</button>`;
    }
    const submit = (ev: Event) => {
      ev.preventDefault();
      const input = (ev.target as HTMLFormElement).querySelector("input")!;
      this._addRoom(input.value);
    };
    return html`<form class="new-room" @submit=${submit}>
      <input
        aria-label=${this._t("add_room_name")}
        placeholder=${this._t("add_room_name")}
        @keydown=${(ev: KeyboardEvent) => ev.key === "Escape" && (this._adding = false)}
      />
      <div class="new-room-buttons">
        <button type="button" class="flat" @click=${() => (this._adding = false)}>${this._t("cancel")}</button>
        <button type="submit" class="primary">${this._t("create")}</button>
      </div>
    </form>`;
  }

  protected updated(changed: PropertyValues): void {
    if (this.hass && !this._rooms && !this._loading && !this._loadError) {
      void this._load();
    }
    // Focus the name field of a new room once, when it opens; not on every
    // update, which would take the focus away from other fields
    if (changed.has("_adding") && this._adding) {
      this.shadowRoot?.querySelector<HTMLInputElement>("form.new-room input")?.focus();
    }
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
    // A room added and discarded is gone again
    if (!this._selected || !(this._selected in this._rooms)) {
      this._selected = Object.keys(this._rooms)[0];
    }
  }

  /** Load the saved configuration again, after asking if that loses changes. */
  private _reload(): void {
    if (this._dirty && !window.confirm(this._t("reload_confirm"))) {
      return;
    }
    this._loadError = undefined;
    void this._load();
  }

  private async _save(force = false): Promise<void> {
    if (!this._rooms || !this._revision) {
      return;
    }
    // Edits replace this._rooms; ones made while saving must survive
    const edited = this._rooms;
    const rooms: Rooms = {};
    for (const [id, room] of Object.entries(edited)) {
      rooms[id] = clean(room);
    }
    this._saving = true;
    try {
      // All rooms: the save covers them all, also those not on screen
      const check = await this.hass.callWS<Check>({ type: "av_scenes/config/validate", rooms });
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
      if (this._rooms === edited) {
        this._rooms = rooms;
      }
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
      return html`<div class="banner error">
        ${this._t("load_error", { error: this._loadError })}
        <button class="flat" @click=${() => this._reload()}>${this._t("retry")}</button>
      </div>`;
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
        ${this._renderAddRoom()}
      </nav>
      <main>
        <av-scenes-guide .language=${this.hass.language}></av-scenes-guide>
        ${this._renderBanner()}
        ${selected
          ? html`<av-scenes-room-editor
                .hass=${this.hass}
                .room=${this._rooms[selected]}
                .roomId=${selected}
                .sources=${this._sources}
                .saved=${(JSON.parse(this._original || "{}") as Rooms)[selected]}
                @room-changed=${(ev: CustomEvent<{ room: Room }>) => this._roomChanged(selected, ev.detail.room)}
                @delete-room=${() => this._deleteRoom(selected)}
              ></av-scenes-room-editor>`
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
          <button class="flat" @click=${() => this._reload()}>${this._t("reload")}</button>
        </div>`;
      case "missing":
        return html`<div class="banner warning">
          ${this._t("missing")}
          <ul>
            ${banner.missing.map(
              (m) => html`<li>
                <code>${m.entity_id}</code> (${this._rooms?.[m.room]?.name ?? m.room}: ${m.path})
              </li>`,
            )}
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
      min-width: 0;
      font-size: 20px;
      margin-left: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
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
    form.new-room {
      display: flex;
      flex-direction: column;
      gap: 6px;
      width: 100%;
    }
    form.new-room input {
      font: inherit;
      padding: 8px 12px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    .new-room-buttons {
      display: flex;
      justify-content: flex-end;
      gap: 4px;
    }
    nav button.flat {
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
    @media (max-width: 600px) {
      /* Room for the buttons: Save is only enabled with unsaved changes anyway */
      .dirty {
        display: none;
      }
      .toolbar button.primary,
      .toolbar button.flat {
        padding: 6px 12px;
      }
    }
  `;
}

if (!customElements.get("av-scenes-panel")) {
  customElements.define("av-scenes-panel", AvScenesPanel);
}
