/** Visual editor of the remote control card. */
import { LitElement, html, nothing, type TemplateResult } from "lit";

import { localize } from "./localize";
import type { CardConfig, HomeAssistant, RoomInfo } from "./types";

export class AvScenesRemoteCardEditor extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
    _rooms: { state: true },
  };

  declare hass?: HomeAssistant;
  declare _config?: CardConfig;
  declare _rooms?: RoomInfo[];

  private _loading = false;

  setConfig(config: CardConfig): void {
    this._config = config;
  }

  protected updated(): void {
    if (this.hass && this._rooms === undefined && !this._loading) {
      this._loading = true;
      this.hass
        .callWS<RoomInfo[]>({ type: "av_scenes/control/rooms" })
        .then((rooms) => (this._rooms = rooms))
        .catch(() => (this._rooms = []))
        .finally(() => (this._loading = false));
    }
  }

  private _schema() {
    // Rooms of different entries may share an id; the entry tells them apart
    const ids = (this._rooms ?? []).map((r) => r.room);
    const options = (this._rooms ?? []).map((r) => ({
      value: ids.filter((id) => id === r.room).length > 1 ? `${r.entry_id}/${r.room}` : r.room,
      label: r.name,
    }));
    return [
      {
        name: "room",
        required: true,
        selector: { select: { mode: "dropdown", options } },
      },
      { name: "name", selector: { text: {} } },
    ];
  }

  protected render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) {
      return nothing;
    }
    const data = {
      ...this._config,
      room: this._config.entry_id ? `${this._config.entry_id}/${this._config.room}` : this._config.room,
    };
    // Keep the configured room selectable while the list loads
    const known = (this._rooms ?? []).some((r) => r.room === this._config!.room);
    if (this._rooms && !known && this._config.room) {
      data.room = this._config.room;
    }
    return html`<ha-form
      .hass=${this.hass}
      .data=${data}
      .schema=${this._schema()}
      .computeLabel=${(s: { name: string }) => localize(this.hass?.language, `editor.${s.name}`)}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }

  private _valueChanged(ev: CustomEvent<{ value: Record<string, unknown> }>): void {
    ev.stopPropagation();
    const value = { ...ev.detail.value };
    const config: Record<string, unknown> = { ...this._config, ...value };
    const room = String(value.room ?? "");
    if (room.includes("/")) {
      const [entryId, roomId] = room.split("/", 2);
      config.entry_id = entryId;
      config.room = roomId;
    } else {
      delete config.entry_id;
    }
    if (!config.name) {
      delete config.name;
    }
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  }
}

if (!customElements.get("av-scenes-remote-card-editor")) {
  customElements.define("av-scenes-remote-card-editor", AvScenesRemoteCardEditor);
}
