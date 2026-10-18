/**
 * Preview of the remote control card while an activity runs.
 *
 * The integration computes the card's view and where each button goes
 * (av_scenes/config/remote) from the room as it is being edited. The real
 * card shows it; a tap sends nothing but tells where the button would go.
 */
import { LitElement, css, html, nothing, type TemplateResult } from "lit";

import "../av-scenes-card";
import { commandLabel } from "../labels";
import type { HomeAssistant, RoomView } from "../types";
import type { Room } from "./model";
import { t } from "./strings";

type Target = {
  via: "activity_commands" | "device_commands" | "remote" | "media_player" | "entity" | null;
  device: string | null;
  entity_id?: string;
  action?: string;
  key?: string;
  actions?: string[];
  ready?: boolean;
};

type Route = {
  group: string;
  device: string | null;
  mode: "auto" | "set" | "hidden";
  commands: string[];
};

type Preview =
  | { error: { path: string[]; message: string } }
  | { error: null; view: RoomView; targets: Record<string, Target>; routes: Route[] };

/** Wait this long after the last change before asking again. */
const DEBOUNCE = 400;

export class AvScenesRemotePreview extends LitElement {
  static properties = {
    hass: { attribute: false },
    room: { attribute: false },
    roomId: { attribute: false },
    activityId: { attribute: false },
    _preview: { state: true },
    _failed: { state: true },
    _pressed: { state: true },
  };

  declare hass: HomeAssistant;
  declare room: Room;
  declare roomId: string;
  declare activityId: string;
  declare _preview?: Preview;
  declare _failed?: string;
  /** The button tapped last: "command|device". */
  declare _pressed?: string;

  private _timer?: number;
  private _request = 0;

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearTimeout(this._timer);
  }

  protected willUpdate(changed: Map<string, unknown>): void {
    if (changed.has("activityId")) {
      this._pressed = undefined;
    }
    if (["room", "roomId", "activityId"].some((key) => changed.has(key))) {
      window.clearTimeout(this._timer);
      const first = this._preview === undefined && this._failed === undefined;
      this._timer = window.setTimeout(() => this._load(), first ? 0 : DEBOUNCE);
    }
  }

  private async _load(): Promise<void> {
    const request = ++this._request;
    try {
      const preview = await this.hass.callWS<Preview>({
        type: "av_scenes/config/remote",
        room: this.roomId,
        config: this.room,
        activity: this.activityId,
      });
      if (request === this._request) {
        this._preview = preview;
        this._failed = undefined;
      }
    } catch (err) {
      if (request === this._request) {
        this._failed = (err as { message?: string }).message ?? String(err);
      }
    }
  }

  private _t(key: string, params?: Record<string, string>): string {
    return t(this.hass?.language, key, params);
  }

  private _entity(entityId: unknown): string {
    const id = String(entityId ?? "");
    return (this.hass.states[id]?.attributes.friendly_name as string | undefined) || id;
  }

  private _device(deviceId: unknown): string {
    const id = String(deviceId ?? "");
    const device = this.room.devices?.[id];
    return device?.name || (device?.entity_id ? this._entity(device.entity_id) : "") || id;
  }

  /** The label the card shows for a button. */
  private _button(view: RoomView, key: string): string {
    const [command, device] = key.split("|");
    const custom = view.remote?.buttons.find((b) => b.command === command && (b.device ?? "") === device);
    if (custom?.name) {
      return custom.name;
    }
    const setting = view.remote?.settings?.find((s) => s.command === command && s.device === device);
    if (setting?.setting === "entity") {
      return setting.label || this._entity(setting.entity_id);
    }
    return commandLabel(command, (key) => this._t(key));
  }

  private _onCall(ev: CustomEvent<{ service: string; data: Record<string, unknown> }>): void {
    const { service, data } = ev.detail;
    if (service === "send_command") {
      this._pressed = `${data.command}|${(data.device as string | undefined) ?? ""}`;
    }
  }

  /** Where a button goes and what runs there, in words. */
  private _describe(target: Target): { to: string; how: string } {
    const to = target.device ? this._device(target.device) : this._t("preview.this_activity");
    switch (target.via) {
      case "media_player":
      case "entity":
        return { to, how: `${target.action} → ${this._entity(target.entity_id)}` };
      case "remote":
        return {
          to,
          how: `remote.send_command "${target.key}" → ${this._entity(target.entity_id)}`,
        };
      case "device_commands":
        return { to, how: this._t("preview.device_commands", { actions: (target.actions ?? []).join(", ") }) };
      case "activity_commands":
        return { to, how: this._t("preview.activity_commands", { actions: (target.actions ?? []).join(", ") }) };
      default:
        return {
          to,
          how: target.device
            ? this._t("preview.unknown_on_device", { device: to })
            : this._t("preview.unknown"),
        };
    }
  }

  private _renderPressed(view: RoomView, targets: Record<string, Target>): TemplateResult {
    const target = this._pressed ? targets[this._pressed] : undefined;
    if (!this._pressed || !target) {
      return html`<p class="pressed hint">${this._t("preview.tap")}</p>`;
    }
    const { to, how } = this._describe(target);
    return html`<p class="pressed ${target.via ? "" : "bad"}">
      <span class="what">${this._button(view, this._pressed)} → ${to}</span>
      <span class="how">${how}</span>
      ${target.ready ? html`<span class="note">${this._t("preview.ready")}</span>` : nothing}
    </p>`;
  }

  private _renderRoutes(routes: Route[]): TemplateResult {
    return html`<h4>${this._t("preview.groups")}</h4>
      <ul class="routes">
        ${routes.map((route) => {
          const where =
            route.mode === "hidden"
              ? this._t("preview.hidden")
              : route.device
                ? `${this._device(route.device)} (${this._t(`preview.mode_${route.mode}`)})`
                : this._t("preview.no_device");
          const keys = route.commands.length
            ? route.commands.map((c) => commandLabel(c, (key) => this._t(key))).join(", ")
            : route.mode === "hidden"
              ? ""
              : route.device
                ? this._t("preview.no_keys", { device: this._device(route.device) })
                : "";
          return html`<li class=${route.commands.length ? "" : "off"}>
            <span class="group">${this._t(`field.${route.group}`)}</span>
            <span class="where">${where}</span>
            ${keys ? html`<span class="keys">${keys}</span>` : nothing}
          </li>`;
        })}
      </ul>`;
  }

  protected render(): TemplateResult {
    if (this._failed) {
      return html`<p class="error">${this._t("flow.failed", { error: this._failed })}</p>`;
    }
    const preview = this._preview;
    if (!preview) {
      return html`<p class="hint">${this._t("loading")}</p>`;
    }
    if (preview.error) {
      const path = preview.error.path.join(".");
      return html`<p class="error">
        ${this._t("flow.invalid", { error: path ? `${path}: ${preview.error.message}` : preview.error.message })}
      </p>`;
    }
    const { view, targets, routes } = preview;
    const dead = Object.entries(targets).filter(([, target]) => !target.via);
    return html`<div class="layout">
      <div class="card">
        <av-scenes-remote-card
          .hass=${this.hass}
          .preview=${view}
          @preview-call=${this._onCall}
        ></av-scenes-remote-card>
      </div>
      <div class="info">
        ${this._renderPressed(view, targets)}
        ${dead.length
          ? html`<div class="dead">
              <span>${this._t("preview.dead")}</span>
              <ul>
                ${dead.map(([key, target]) => html`<li>${this._button(view, key)}: ${this._describe(target).how}</li>`)}
              </ul>
            </div>`
          : nothing}
        ${this._renderRoutes(routes)}
      </div>
    </div>`;
  }

  static styles = css`
    :host {
      display: block;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 360px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    @media (max-width: 700px) {
      .layout {
        grid-template-columns: minmax(0, 1fr);
      }
    }
    .card {
      max-width: 360px;
    }
    .pressed {
      display: flex;
      flex-direction: column;
      gap: 2px;
      margin: 0 0 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: var(--secondary-background-color);
      overflow-wrap: anywhere;
    }
    .pressed.hint {
      color: var(--secondary-text-color);
    }
    .pressed.bad {
      color: var(--error-color, #db4437);
    }
    .what {
      font-weight: 500;
    }
    .how {
      font-family: var(--code-font-family, monospace);
      font-size: 0.85em;
    }
    .note {
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .dead {
      color: var(--error-color, #db4437);
      font-size: 0.9em;
      margin-bottom: 12px;
    }
    .dead ul {
      margin: 4px 0 0;
      padding-left: 20px;
    }
    h4 {
      font-size: 0.95em;
      font-weight: 500;
      margin: 0 0 6px;
    }
    ul.routes {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    ul.routes li {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 0 8px;
      padding: 6px 0;
      border-top: 1px solid var(--divider-color);
    }
    ul.routes li:first-child {
      border-top: none;
    }
    ul.routes li.off .where {
      color: var(--secondary-text-color);
    }
    .group {
      font-weight: 500;
    }
    .keys {
      grid-column: 2;
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .error {
      color: var(--error-color, #db4437);
      margin: 0;
    }
    p.hint {
      color: var(--secondary-text-color);
    }
  `;
}

if (!customElements.get("av-scenes-remote-preview")) {
  customElements.define("av-scenes-remote-preview", AvScenesRemotePreview);
}
