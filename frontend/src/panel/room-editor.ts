/**
 * Editor of one room: devices, activities and a YAML view. All fields are
 * Home Assistant's own ha-form selectors; changes are sent up as
 * "room-changed" events and saved by the panel.
 */
import { LitElement, css, html, nothing, type TemplateResult } from "lit";

import type { HomeAssistant } from "../types";
import {
  GROUPS,
  STEP_TYPES,
  clean,
  deviceUsage,
  renameDevice,
  slugify,
  stepSchema,
  uniqueKey,
  type Activity,
  type Device,
  type Obj,
  type Room,
  type Step,
} from "./model";
import { t } from "./strings";

type Tab = "devices" | "activities" | "yaml";

const SECONDS = { number: { min: 0, max: 3600, step: 1, mode: "box", unit_of_measurement: "s" } };

export class AvScenesRoomEditor extends LitElement {
  static properties = {
    hass: { attribute: false },
    room: { attribute: false },
    roomId: { attribute: false },
    _tab: { state: true },
    _open: { state: true },
    _notice: { state: true },
  };

  declare hass: HomeAssistant;
  declare room: Room;
  declare roomId: string;
  declare _tab: Tab;
  declare _open: Set<string>;
  declare _notice?: string;

  constructor() {
    super();
    this._tab = "devices";
    this._open = new Set();
  }

  private _t(key: string, params?: Record<string, string>): string {
    return t(this.hass?.language, key, params);
  }

  private _label = (schema: { name: string }): string => this._t(`field.${schema.name}`);

  private _emit(room: Room): void {
    this.dispatchEvent(new CustomEvent("room-changed", { detail: { room } }));
  }

  private _toggle(key: string, open: boolean): void {
    const next = new Set(this._open);
    if (open) next.add(key);
    else next.delete(key);
    this._open = next;
  }

  // ------------------------------------------------------------------

  protected render(): TemplateResult {
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${{ name: this.room.name ?? "", area_id: this.room.area_id ?? undefined }}
        .schema=${[
          { name: "name", required: true, selector: { text: {} } },
          { name: "area_id", selector: { area: {} } },
        ]}
        .computeLabel=${(s: { name: string }) => this._t(s.name === "name" ? "room_name" : "room_area")}
        @value-changed=${(ev: CustomEvent) => {
          const v = ev.detail.value as Obj;
          this._emit(clean({ ...this.room, name: v.name as string, area_id: v.area_id as string }));
        }}
      ></ha-form>
      <div class="hint">${this._t("room_id_hint", { id: this.roomId })}</div>

      <div class="tabs" role="tablist">
        ${(["devices", "activities", "yaml"] as Tab[]).map(
          (tab) => html`<button
            role="tab"
            class=${this._tab === tab ? "active" : ""}
            aria-selected=${this._tab === tab ? "true" : "false"}
            @click=${() => (this._tab = tab)}
          >
            ${this._t(`tab_${tab}`)}
          </button>`,
        )}
      </div>
      ${this._notice ? html`<div class="notice">${this._notice}</div>` : nothing}
      ${this._tab === "devices"
        ? this._renderDevices()
        : this._tab === "activities"
          ? this._renderActivities()
          : this._renderYaml()}
    `;
  }

  // ------------------------------------------------------------------
  // Devices
  // ------------------------------------------------------------------

  private _renderDevices(): TemplateResult {
    const devices = Object.entries(this.room.devices ?? {});
    return html`
      ${devices.map(([id, device]) => this._renderDevice(id, device))}
      <button class="add" @click=${this._addDevice}>+ ${this._t("add_device")}</button>
    `;
  }

  private _renderDevice(id: string, device: Device): TemplateResult {
    const key = `d:${id}`;
    const ready = device.ready ?? null;
    const data: Obj = {
      entity_id: device.entity_id,
      name: device.name,
      power_switch: device.power_switch ?? undefined,
      delay_after_power: device.delay_after_power,
      delay_after_on: device.delay_after_on,
      delay_after_off: device.delay_after_off,
      ready_enabled: ready !== null,
      ready_timeout: ready?.timeout,
      ready_reload: ready?.reload_integration,
      ready_on_timeout: ready?.on_timeout,
      commands: device.commands,
    };
    const schema: Obj[] = [
      { name: "entity_id", required: true, selector: { entity: {} } },
      { name: "name", selector: { text: {} } },
      { name: "power_switch", selector: { entity: { filter: { domain: ["switch", "input_boolean", "light"] } } } },
      { name: "delay_after_power", selector: SECONDS },
      { name: "delay_after_on", selector: SECONDS },
      { name: "delay_after_off", selector: SECONDS },
      { name: "ready_enabled", selector: { boolean: {} } },
      ...(ready !== null
        ? [
            { name: "ready_timeout", selector: SECONDS },
            { name: "ready_reload", selector: { boolean: {} } },
            {
              name: "ready_on_timeout",
              selector: {
                select: {
                  options: [
                    { value: "abort", label: this._t("on_timeout_abort") },
                    { value: "continue", label: this._t("on_timeout_continue") },
                  ],
                  mode: "dropdown",
                },
              },
            },
          ]
        : []),
      { name: "commands", selector: { object: {} } },
    ];
    const state = device.entity_id ? this.hass.states[device.entity_id] : undefined;
    return html`<details
      class="item"
      ?open=${this._open.has(key)}
      @toggle=${(ev: Event) => this._toggle(key, (ev.target as HTMLDetailsElement).open)}
    >
      <summary>
        <span class="title">${device.name || (state?.attributes.friendly_name as string) || id}</span>
        <span class="sub">${device.entity_id || "—"}</span>
      </summary>
      ${this._open.has(key)
        ? html`<div class="item-body">
            <div class="row">
              <label class="id">
                ${this._t("device_id")}
                <input
                  .value=${id}
                  @change=${(ev: Event) => this._renameDevice(id, (ev.target as HTMLInputElement).value)}
                />
              </label>
              <button class="danger" @click=${() => this._deleteDevice(id)}>${this._t("delete")}</button>
            </div>
            <ha-form
              .hass=${this.hass}
              .data=${data}
              .schema=${schema}
              .computeLabel=${(s: { name: string }) => this._t(`field.${s.name}`)}
              @value-changed=${(ev: CustomEvent) => this._deviceChanged(id, ev.detail.value as Obj)}
            ></ha-form>
          </div>`
        : nothing}
    </details>`;
  }

  private _deviceChanged(id: string, v: Obj): void {
    const device = clean({
      entity_id: v.entity_id as string,
      name: v.name as string | undefined,
      power_switch: v.power_switch as string | undefined,
      ready: v.ready_enabled
        ? clean({
            timeout: v.ready_timeout as number | undefined,
            reload_integration: v.ready_reload as boolean | undefined,
            on_timeout: v.ready_on_timeout as string | undefined,
          })
        : undefined,
      delay_after_power: v.delay_after_power as number | undefined,
      delay_after_on: v.delay_after_on as number | undefined,
      delay_after_off: v.delay_after_off as number | undefined,
      commands: v.commands as Obj | undefined,
    }) as Device;
    // An enabled check without options is still a check
    if (v.ready_enabled && !device.ready) {
      device.ready = {};
    }
    this._emit({ ...this.room, devices: { ...this.room.devices, [id]: device } });
  }

  private _addDevice(): void {
    const id = uniqueKey("device", Object.keys(this.room.devices ?? {}));
    this._toggle(`d:${id}`, true);
    this._emit({ ...this.room, devices: { ...this.room.devices, [id]: { entity_id: "" } } });
  }

  private _renameDevice(from: string, raw: string): void {
    const to = slugify(raw);
    if (!to || to === from) {
      this.requestUpdate();
      return;
    }
    const id = uniqueKey(to, Object.keys(this.room.devices ?? {}).filter((k) => k !== from));
    this._toggle(`d:${from}`, false);
    this._toggle(`d:${id}`, true);
    this._emit(renameDevice(this.room, from, id));
  }

  private _deleteDevice(id: string): void {
    const where = deviceUsage(this.room, id);
    if (where.length) {
      this._notice = this._t("device_in_use", { id, where: where.join(", ") });
      return;
    }
    this._notice = undefined;
    const devices = { ...this.room.devices };
    delete devices[id];
    this._emit({ ...this.room, devices });
  }

  // ------------------------------------------------------------------
  // Activities
  // ------------------------------------------------------------------

  private _renderActivities(): TemplateResult {
    const activities = Object.entries(this.room.activities ?? {}).sort(
      ([ka, a], [kb, b]) =>
        (a.order ?? 1000) - (b.order ?? 1000) ||
        (a.name ?? ka).localeCompare(b.name ?? kb, undefined, { sensitivity: "base" }),
    );
    return html`
      ${activities.map(([id, activity]) => this._renderActivity(id, activity))}
      <button class="add" @click=${this._addActivity}>+ ${this._t("add_activity")}</button>
    `;
  }

  private _setActivity(id: string, activity: Activity): void {
    this._emit({ ...this.room, activities: { ...this.room.activities, [id]: clean(activity) } });
  }

  private _renderActivity(id: string, activity: Activity): TemplateResult {
    const key = `a:${id}`;
    return html`<details
      class="item"
      ?open=${this._open.has(key)}
      @toggle=${(ev: Event) => this._toggle(key, (ev.target as HTMLDetailsElement).open)}
    >
      <summary>
        ${activity.icon ? html`<ha-icon .icon=${activity.icon}></ha-icon>` : nothing}
        <span class="title">${activity.name ?? id}</span>
        <span class="sub">${(activity.devices ?? []).join(" → ")}</span>
      </summary>
      ${this._open.has(key) ? this._renderActivityBody(id, activity) : nothing}
    </details>`;
  }

  private _renderActivityBody(id: string, activity: Activity): TemplateResult {
    const devices = Object.keys(this.room.devices ?? {});
    const chosen = activity.devices ?? [];
    const routeOptions = [
      { value: "__auto", label: this._t("route_auto") },
      { value: "__none", label: this._t("route_none") },
      ...chosen.map((d) => ({ value: d, label: this.room.devices?.[d]?.name ?? d })),
    ];
    const remote = activity.remote ?? {};
    const remoteData: Obj = {
      buttons: remote.buttons,
      activity_commands: activity.commands,
    };
    for (const g of GROUPS) {
      remoteData[g] = !(g in remote) ? "__auto" : remote[g] === null ? "__none" : remote[g];
    }

    return html`<div class="item-body">
      <div class="row">
        <span class="hint">${this._t("activity_id_hint", { id })}</span>
        <button class="danger" @click=${() => this._deleteActivity(id, activity)}>${this._t("delete")}</button>
      </div>
      <ha-form
        .hass=${this.hass}
        .data=${{ name: activity.name, icon: activity.icon, order: activity.order }}
        .schema=${[
          { name: "name", required: true, selector: { text: {} } },
          { name: "icon", selector: { icon: {} } },
          { name: "order", selector: { number: { min: 0, max: 999, mode: "box" } } },
        ]}
        .computeLabel=${this._label}
        @value-changed=${(ev: CustomEvent) => {
          const v = ev.detail.value as Obj;
          this._setActivity(id, { ...activity, name: v.name as string, icon: v.icon as string, order: v.order as number });
        }}
      ></ha-form>

      <h3>${this._t("devices_of_activity")}</h3>
      <ol class="ordered">
        ${chosen.map(
          (d, i) => html`<li>
            <span>${this.room.devices?.[d]?.name ?? d}</span>
            <span class="sub">${this.room.devices?.[d]?.entity_id ?? ""}</span>
            ${this._moveButtons(chosen, i, (list) => this._setActivity(id, { ...activity, devices: list }))}
          </li>`,
        )}
      </ol>
      ${devices.some((d) => !chosen.includes(d))
        ? this._picker(
            this._t("add_device_to_activity"),
            devices.filter((d) => !chosen.includes(d)).map((d) => ({ value: d, label: this.room.devices?.[d]?.name ?? d })),
            (d) => this._setActivity(id, { ...activity, devices: [...chosen, d] }),
          )
        : nothing}

      <h3>${this._t("steps")}</h3>
      ${(activity.steps ?? []).map((step, i) => this._renderStep(id, activity, step, i))}
      ${this._picker(
        this._t("add_step"),
        STEP_TYPES.map((type) => ({ value: type, label: this._t(`step.${type}`) })),
        (type) => this._setActivity(id, { ...activity, steps: [...(activity.steps ?? []), { type }] }),
      )}

      <details class="section">
        <summary>${this._t("remote")}</summary>
        <ha-form
          .hass=${this.hass}
          .data=${remoteData}
          .schema=${[
            ...GROUPS.map((g) => ({ name: g, selector: { select: { options: routeOptions, mode: "dropdown" } } })),
            { name: "buttons", selector: { object: {} } },
            { name: "activity_commands", selector: { object: {} } },
          ]}
          .computeLabel=${this._label}
          @value-changed=${(ev: CustomEvent) => this._remoteChanged(id, activity, ev.detail.value as Obj)}
        ></ha-form>
      </details>

      <details class="section">
        <summary>${this._t("hooks")}</summary>
        <ha-form
          .hass=${this.hass}
          .data=${{ on_start: activity.on_start ?? [], on_stop: activity.on_stop ?? [] }}
          .schema=${[
            { name: "on_start", selector: { action: {} } },
            { name: "on_stop", selector: { action: {} } },
          ]}
          .computeLabel=${this._label}
          @value-changed=${(ev: CustomEvent) => {
            const v = ev.detail.value as Obj;
            this._setActivity(id, { ...activity, on_start: v.on_start as unknown[], on_stop: v.on_stop as unknown[] });
          }}
        ></ha-form>
      </details>
    </div>`;
  }

  private _renderStep(id: string, activity: Activity, step: Step, index: number): TemplateResult {
    const steps = activity.steps ?? [];
    const setSteps = (list: Step[]) => this._setActivity(id, { ...activity, steps: list });
    return html`<div class="step">
      <div class="step-head">
        <span class="title">${index + 1}. ${this._t(`step.${step.type}`)}</span>
        ${this._moveButtons(steps, index, setSteps)}
      </div>
      <ha-form
        .hass=${this.hass}
        .data=${step}
        .schema=${stepSchema(this.hass, this.room, step, (k) => this._t(k))}
        .computeLabel=${this._label}
        @value-changed=${(ev: CustomEvent) => {
          const list = [...steps];
          list[index] = clean({ ...(ev.detail.value as Step), type: step.type });
          setSteps(list);
        }}
      ></ha-form>
    </div>`;
  }

  private _remoteChanged(id: string, activity: Activity, v: Obj): void {
    const remote: Obj = {};
    for (const g of GROUPS) {
      if (v[g] === "__none") remote[g] = null;
      else if (v[g] && v[g] !== "__auto") remote[g] = v[g];
    }
    if (Array.isArray(v.buttons) && v.buttons.length) {
      remote.buttons = v.buttons;
    }
    this._setActivity(id, {
      ...activity,
      remote: Object.keys(remote).length ? remote : undefined,
      commands: v.activity_commands as Obj | undefined,
    });
  }

  private _addActivity(): void {
    const name = this._t("new_activity");
    const id = uniqueKey(slugify(name), Object.keys(this.room.activities ?? {}));
    this._toggle(`a:${id}`, true);
    this._setActivity(id, { name, devices: [] });
  }

  private _deleteActivity(id: string, activity: Activity): void {
    if (!window.confirm(`${this._t("delete")}: ${activity.name ?? id}?`)) {
      return;
    }
    const activities = { ...this.room.activities };
    delete activities[id];
    this._emit({ ...this.room, activities });
  }

  // ------------------------------------------------------------------
  // YAML
  // ------------------------------------------------------------------

  private _renderYaml(): TemplateResult {
    return html`<ha-form
      .hass=${this.hass}
      .data=${{ yaml: this.room }}
      .schema=${[{ name: "yaml", selector: { object: {} } }]}
      .computeLabel=${() => ""}
      @value-changed=${(ev: CustomEvent) => {
        const value = (ev.detail.value as Obj).yaml;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          this._emit(value as Room);
        }
      }}
    ></ha-form>`;
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  private _moveButtons<T>(list: T[], index: number, set: (list: T[]) => void): TemplateResult {
    const move = (to: number) => {
      const next = [...list];
      const [item] = next.splice(index, 1);
      next.splice(to, 0, item);
      set(next);
    };
    return html`<span class="move">
      <button title=${this._t("move_up")} ?disabled=${index === 0} @click=${() => move(index - 1)}>
        <ha-icon icon="mdi:arrow-up"></ha-icon>
      </button>
      <button title=${this._t("move_down")} ?disabled=${index === list.length - 1} @click=${() => move(index + 1)}>
        <ha-icon icon="mdi:arrow-down"></ha-icon>
      </button>
      <button title=${this._t("delete")} @click=${() => set(list.filter((_, i) => i !== index))}>
        <ha-icon icon="mdi:close"></ha-icon>
      </button>
    </span>`;
  }

  /** A dropdown that adds the chosen value and resets itself. */
  private _picker(
    label: string,
    options: { value: string; label: string }[],
    pick: (value: string) => void,
  ): TemplateResult {
    return html`<ha-form
      class="picker"
      .hass=${this.hass}
      .data=${{ pick: undefined }}
      .schema=${[{ name: "pick", selector: { select: { options, mode: "dropdown" } } }]}
      .computeLabel=${() => label}
      @value-changed=${(ev: CustomEvent) => {
        const value = (ev.detail.value as Obj).pick as string | undefined;
        if (value) {
          pick(value);
          (ev.target as LitElement).requestUpdate();
        }
      }}
    ></ha-form>`;
  }

  static styles = css`
    :host {
      display: block;
    }
    .hint,
    .sub {
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    .tabs {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--divider-color);
      margin: 16px 0;
    }
    .tabs button {
      font: inherit;
      background: none;
      border: none;
      padding: 8px 16px;
      cursor: pointer;
      color: var(--secondary-text-color);
      border-bottom: 2px solid transparent;
    }
    .tabs button.active {
      color: var(--primary-color);
      border-bottom-color: var(--primary-color);
    }
    .notice {
      background: var(--warning-color, #ffa600);
      color: var(--text-primary-color, #fff);
      padding: 8px 12px;
      border-radius: 8px;
      margin-bottom: 12px;
    }
    details.item {
      border: 1px solid var(--divider-color);
      border-radius: 12px;
      margin-bottom: 8px;
      background: var(--card-background-color);
    }
    details.item > summary {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      cursor: pointer;
      flex-wrap: wrap;
    }
    .title {
      font-weight: 500;
    }
    .item-body {
      padding: 0 16px 16px;
    }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    label.id {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--secondary-text-color);
    }
    label.id input {
      font: inherit;
      padding: 6px 8px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    h3 {
      font-size: 1em;
      font-weight: 500;
      margin: 20px 0 8px;
    }
    ol.ordered {
      margin: 0 0 8px;
      padding-left: 24px;
    }
    ol.ordered li {
      padding: 2px 0;
    }
    ol.ordered li > span:first-child {
      margin-right: 8px;
    }
    .step {
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      padding: 8px 12px;
      margin-bottom: 8px;
    }
    .step-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .move {
      display: inline-flex;
      gap: 2px;
      vertical-align: middle;
    }
    .move button {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--secondary-text-color);
      padding: 4px;
      --mdc-icon-size: 18px;
    }
    .move button:disabled {
      opacity: 0.3;
      cursor: default;
    }
    details.section {
      margin-top: 16px;
    }
    details.section > summary {
      cursor: pointer;
      font-weight: 500;
      padding: 8px 0;
    }
    button.add,
    button.danger {
      font: inherit;
      border: none;
      border-radius: 8px;
      padding: 8px 14px;
      cursor: pointer;
    }
    button.add {
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      margin-top: 8px;
    }
    button.danger {
      background: none;
      color: var(--error-color, #db4437);
    }
    .picker {
      display: block;
      max-width: 320px;
    }
  `;
}

if (!customElements.get("av-scenes-room-editor")) {
  customElements.define("av-scenes-room-editor", AvScenesRoomEditor);
}
