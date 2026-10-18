/**
 * The flow of an activity: what a start or stop switches, when and how.
 *
 * Computed by the integration (av_scenes/config/flow) from the room as it
 * is being edited, so it follows every change before it is saved.
 */
import { LitElement, css, html, nothing, type TemplateResult } from "lit";

import type { HomeAssistant } from "../types";
import type { Room } from "./model";
import { t } from "./strings";

type Row = {
  kind: string;
  at: [number, number];
  [key: string]: unknown;
};

type Flow =
  | { error: { path: string[]; message: string } }
  | { error: null; rows: Row[]; done: [number, number] };

type Mode = "start" | "stop";

/** Wait this long after the last change before asking for the flow again. */
const DEBOUNCE = 400;

const ICONS: Record<string, string> = {
  state: "mdi:flag-outline",
  outlets_on: "mdi:power-socket-eu",
  outlets_off: "mdi:power-socket-eu",
  outlet_keep: "mdi:power-socket-eu",
  turn_on: "mdi:power",
  turn_off: "mdi:power-off",
  hook: "mdi:script-text-outline",
  hook_wait: "mdi:script-text-outline",
  boot: "mdi:timer-sand",
  wait: "mdi:timer-sand",
  reload: "mdi:reload",
  ready: "mdi:lan-connect",
  already_on: "mdi:check",
  step: "mdi:tune-variant",
};

/** Rows that belong to the device or steps header above them. */
const NESTED = new Set(["boot", "reload", "ready", "turn_on", "wait", "already_on", "step", "turn_off"]);

export class AvScenesFlow extends LitElement {
  static properties = {
    hass: { attribute: false },
    room: { attribute: false },
    roomId: { attribute: false },
    activityId: { attribute: false },
    _mode: { state: true },
    _from: { state: true },
    _flow: { state: true },
    _failed: { state: true },
  };

  declare hass: HomeAssistant;
  declare room: Room;
  declare roomId: string;
  declare activityId: string;
  declare _mode: Mode;
  /** Start from this activity instead of from idle. */
  declare _from?: string;
  declare _flow?: Flow;
  declare _failed?: string;

  private _timer?: number;
  private _request = 0;

  constructor() {
    super();
    this._mode = "start";
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearTimeout(this._timer);
  }

  protected willUpdate(changed: Map<string, unknown>): void {
    if (changed.has("activityId") && changed.get("activityId") !== undefined) {
      this._from = undefined;
    }
    if (this._from !== undefined && !this.room.activities?.[this._from]) {
      this._from = undefined;
    }
    if (["room", "roomId", "activityId", "_mode", "_from"].some((key) => changed.has(key))) {
      window.clearTimeout(this._timer);
      // Typing in the forms changes the room often; switching the view does not
      const first = this._flow === undefined && this._failed === undefined;
      const delay = !first && changed.has("room") ? DEBOUNCE : 0;
      this._timer = window.setTimeout(() => this._load(), delay);
    }
  }

  private async _load(): Promise<void> {
    const request = ++this._request;
    try {
      const flow = await this.hass.callWS<Flow>({
        type: "av_scenes/config/flow",
        room: this.roomId,
        config: this.room,
        activity: this.activityId,
        mode: this._mode,
        ...(this._mode === "start" && this._from ? { from: this._from } : {}),
      });
      if (request === this._request) {
        this._flow = flow;
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

  // ------------------------------------------------------------------
  // Names
  // ------------------------------------------------------------------

  private _entity(entityId: unknown): string {
    const id = String(entityId ?? "");
    return (this.hass.states[id]?.attributes.friendly_name as string | undefined) || id;
  }

  private _device(deviceId: unknown): string {
    const id = String(deviceId ?? "");
    const device = this.room.devices?.[id];
    return device?.name || (device?.entity_id ? this._entity(device.entity_id) : "") || id;
  }

  private _activity(activityId: unknown): string {
    const id = String(activityId ?? "");
    return this.room.activities?.[id]?.name || id;
  }

  private _list(entities: unknown): string {
    return ((entities as string[] | undefined) ?? []).map((e) => this._entity(e)).join(", ");
  }

  private _seconds(value: unknown): string {
    return `${Math.round(Number(value) * 10) / 10} s`;
  }

  private _time([min, max]: [number, number]): string {
    return min === max ? this._seconds(min) : `${this._seconds(min).slice(0, -2)}–${this._seconds(max)}`;
  }

  // ------------------------------------------------------------------
  // Rows
  // ------------------------------------------------------------------

  /** What a row does, in words. */
  private _text(row: Row): string {
    const device = this._device(row.device);
    switch (row.kind) {
      case "state":
        return this._t(`flow.state_${row.state}`);
      case "outlets_on":
        return this._t("flow.outlets_on", { outlets: this._list(row.entities) });
      case "outlets_off":
        return this._t(row.background ? "flow.outlets_off_later" : "flow.outlets_off", {
          outlets: this._list(row.entities),
        });
      case "outlet_keep":
        return this._t("flow.outlet_keep", { outlet: this._entity(row.entity_id) });
      case "hook":
        return this._t(`flow.${row.hook}`);
      case "hook_wait":
        return this._t(`flow.${row.hook}_wait`);
      case "already_on":
        return this._t("flow.already_on", { activity: this._activity(row.previous) });
      case "boot":
        return this._t("flow.boot", { seconds: this._seconds(row.seconds) });
      case "reload":
        return this._t("flow.reload", { entity: this._entity(row.entity_id) });
      case "ready": {
        const states = (Array.isArray(row.states) ? row.states : row.states ? [row.states] : []) as string[];
        const params = {
          entity: this._entity(row.entity_id),
          states: states.join(" / "),
          timeout: this._seconds(row.timeout),
        };
        return [
          row.step ? `${row.step}. ` : "",
          this._t(states.length ? "flow.ready_state" : "flow.ready", params),
          " ",
          this._t(`flow.on_timeout_${row.on_timeout}`),
        ].join("");
      }
      case "turn_on":
      case "turn_off": {
        const prefix = row.step ? `${row.step}. ` : "";
        if (row.skip) {
          return prefix + this._t("flow.cannot_switch", { device });
        }
        return prefix + this._t(row.reason === "unused" ? "flow.turn_off_unused" : `flow.${row.kind}`, { device });
      }
      case "wait":
        return this._t(row.reason === "delay_after_on" ? "flow.wait_on" : "flow.wait", {
          seconds: this._seconds(row.seconds),
        });
      case "step":
        return `${row.step}. ${this._t(`step.${row.step_type}`)}${this._stepValue(row)}`;
      default:
        return row.kind;
    }
  }

  /** The value a step sets, e.g. ": SAT" or ": 35 %". */
  private _stepValue(row: Row): string {
    const data = (row.data ?? {}) as Record<string, unknown>;
    const parts: string[] = [];
    for (const [key, value] of Object.entries(data)) {
      if (key === "volume_level") parts.push(`${Math.round(Number(value) * 100)} %`);
      else if (key === "brightness_pct" || key === "position" || key === "tilt_position") parts.push(`${value} %`);
      else if (key === "color_temp_kelvin") parts.push(`${value} K`);
      else if (key === "transition") parts.push(this._seconds(value));
      else if (row.step_type !== "call_action") parts.push(String(value));
    }
    return parts.length ? `: ${parts.join(", ")}` : "";
  }

  /** Small notes: conditions, cool-downs, rooms that keep an outlet on. */
  private _notes(row: Row): string[] {
    const notes: string[] = [];
    if (typeof row.condition === "string") notes.push(this._t(`flow.if.${row.condition}`));
    if (row.kind === "ready" && row.reload) notes.push(this._t("flow.reload_if_needed"));
    if (row.kind === "turn_off" && Number(row.cooldown) > 0) {
      notes.push(this._t("flow.cooldown", { seconds: this._seconds(row.cooldown) }));
    }
    if (Array.isArray(row.already_on) && row.already_on.length) {
      notes.push(this._t("flow.outlets_already_on", { outlets: this._list(row.already_on) }));
    }
    if (Array.isArray(row.unless_rooms) && row.unless_rooms.length) {
      notes.push(this._t("flow.unless_rooms", { rooms: (row.unless_rooms as string[]).join(", ") }));
    }
    if (row.kind === "hook") {
      const actions = (row.actions as string[] | undefined) ?? [];
      notes.push(this._t("flow.parallel"));
      if (actions.length) notes.push(actions.join(", "));
    }
    return notes;
  }

  /** The action and its targets, as Home Assistant calls it. */
  private _call(row: Row): string | undefined {
    if (typeof row.action !== "string" || row.kind === "hook") {
      return undefined;
    }
    const target = row.entities ? this._list(row.entities) : row.entity_id ? this._entity(row.entity_id) : "";
    return target ? `${row.action} → ${target}` : row.action;
  }

  private _renderRow(row: Row, nested: boolean, showTime: boolean): TemplateResult {
    const notes = this._notes(row);
    const call = this._call(row);
    const header = row.kind === "device" || row.kind === "steps";
    return html`<li class=${[nested ? "nested" : "", header ? "header" : "", row.kind].join(" ")}>
      <span class="time">${showTime ? this._time(row.at) : ""}</span>
      ${header
        ? html`<span class="index">${row.kind === "device" ? row.index : "≡"}</span>`
        : html`<ha-icon class="icon" .icon=${ICONS[row.kind] ?? "mdi:circle-small"}></ha-icon>`}
      <span class="body">
        <span class="what"
          >${row.kind === "device"
            ? this._device(row.device)
            : row.kind === "steps"
              ? this._t("flow.steps")
              : this._text(row)}</span
        >
        ${row.kind === "device" ? html`<span class="call">${row.entity_id}</span>` : nothing}
        ${call ? html`<span class="call">${call}</span>` : nothing}
        ${notes.length ? html`<span class="notes">${notes.map((n) => html`<span class="note">${n}</span>`)}</span>` : nothing}
      </span>
    </li>`;
  }

  private _renderRows(rows: Row[]): TemplateResult {
    const foreground = rows.filter((row) => !row.background);
    const background = rows.filter((row) => row.background);
    let group = false;
    let last = "";
    const items = foreground.map((row) => {
      if (row.kind === "device" || row.kind === "steps") group = true;
      else if (!NESTED.has(row.kind) || row.reason === "unused") group = false;
      const time = this._time(row.at);
      const show = time !== last || row.kind === "state";
      last = time;
      return this._renderRow(row, group && row.kind !== "device" && row.kind !== "steps", show);
    });
    return html`<ol class="flow">${items}</ol>
      ${background.length
        ? html`<h4>${this._t("flow.background")}</h4>
            <ol class="flow">${background.map((row) => this._renderRow(row, false, true))}</ol>`
        : nothing}`;
  }

  // ------------------------------------------------------------------

  protected render(): TemplateResult {
    const others = Object.entries(this.room.activities ?? {}).filter(([id]) => id !== this.activityId);
    return html`
      <div class="modes" role="tablist">
        ${(["start", "stop"] as Mode[]).map(
          (mode) => html`<button
            role="tab"
            class=${this._mode === mode ? "active" : ""}
            aria-selected=${this._mode === mode ? "true" : "false"}
            @click=${() => (this._mode = mode)}
          >
            ${this._t(`flow.mode_${mode}`)}
          </button>`,
        )}
        ${this._mode === "start" && others.length
          ? html`<select
              aria-label=${this._t("flow.from_label")}
              @change=${(ev: Event) => {
                const value = (ev.target as HTMLSelectElement).value;
                this._from = value || undefined;
              }}
            >
              <option value="" ?selected=${!this._from}>${this._t("flow.from_idle")}</option>
              ${others.map(
                ([id, activity]) =>
                  html`<option value=${id} ?selected=${this._from === id}>
                    ${this._t("flow.from", { activity: activity.name || id })}
                  </option>`,
              )}
            </select>`
          : nothing}
      </div>
      ${this._renderBody()}
    `;
  }

  private _renderBody(): TemplateResult {
    if (this._failed) {
      return html`<p class="error">${this._t("flow.failed", { error: this._failed })}</p>`;
    }
    const flow = this._flow;
    if (!flow) {
      return html`<p class="hint">${this._t("loading")}</p>`;
    }
    if (flow.error) {
      const path = flow.error.path.join(".");
      return html`<p class="error">
        ${this._t("flow.invalid", { error: path ? `${path}: ${flow.error.message}` : flow.error.message })}
      </p>`;
    }
    const [min, max] = flow.done;
    const background = flow.rows.filter((row) => row.background).map((row) => row.at[0]);
    const summary =
      this._mode === "start"
        ? this._t(min === max ? "flow.summary_start_fixed" : "flow.summary_start", {
            min: this._seconds(min),
            max: this._seconds(max),
          })
        : this._t(background.length ? "flow.summary_stop_cut" : "flow.summary_stop", {
            seconds: this._seconds(Math.max(0, ...background)),
          });
    return html`${this._renderRows(flow.rows)}
      <p class="summary">${summary}</p>`;
  }

  static styles = css`
    :host {
      display: block;
    }
    .modes {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
    }
    .modes button {
      font: inherit;
      padding: 6px 14px;
      border-radius: 16px;
      border: 1px solid var(--divider-color);
      background: none;
      color: var(--primary-text-color);
      cursor: pointer;
    }
    .modes button.active {
      background: var(--primary-color);
      border-color: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .modes select {
      font: inherit;
      padding: 6px 8px;
      border-radius: 8px;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color);
      color: var(--primary-text-color);
      max-width: 100%;
    }
    ol.flow {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    ol.flow li {
      display: grid;
      grid-template-columns: 64px 24px minmax(0, 1fr);
      gap: 4px 10px;
      align-items: start;
      padding: 6px 0;
      border-top: 1px solid var(--divider-color);
    }
    ol.flow li:first-child {
      border-top: none;
    }
    ol.flow li.nested {
      grid-template-columns: 64px 40px minmax(0, 1fr);
      border-top: none;
      padding-top: 2px;
    }
    ol.flow li.nested .icon {
      justify-self: end;
    }
    .time {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      text-align: right;
      padding-top: 2px;
    }
    .icon {
      --mdc-icon-size: 20px;
      color: var(--secondary-text-color);
    }
    li.state .icon,
    li.state .what {
      color: var(--primary-color);
    }
    li.state .what,
    li.header .what {
      font-weight: 500;
    }
    .index {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--secondary-background-color);
      font-size: 0.8em;
      font-weight: 500;
    }
    .body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .call {
      font-family: var(--code-font-family, monospace);
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .notes {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }
    .note {
      font-size: 0.8em;
      padding: 1px 8px;
      border-radius: 10px;
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
    }
    h4 {
      font-size: 0.95em;
      font-weight: 500;
      margin: 16px 0 4px;
    }
    .summary {
      margin: 12px 0 0;
      font-size: 0.9em;
      color: var(--secondary-text-color);
      line-height: 1.4;
    }
    .error {
      color: var(--error-color, #db4437);
      margin: 0;
    }
    .hint {
      color: var(--secondary-text-color);
      margin: 0;
    }
    @media (max-width: 450px) {
      ol.flow li {
        grid-template-columns: 58px 22px minmax(0, 1fr);
        gap: 4px 6px;
      }
      ol.flow li.nested {
        grid-template-columns: 58px 32px minmax(0, 1fr);
      }
      .time {
        font-size: 0.75em;
      }
    }
  `;
}

if (!customElements.get("av-scenes-flow")) {
  customElements.define("av-scenes-flow", AvScenesFlow);
}
