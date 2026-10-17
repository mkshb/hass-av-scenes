/**
 * AV Scenes remote control card.
 *
 * The card subscribes to av_scenes/control/subscribe for its room and shows
 * only what the running activity offers. Everything it does goes through the
 * integration's services, so the same commands work from automations.
 */
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";

import "./editor";
import { localize } from "./localize";
import { clock, nowPlaying, type NowPlaying } from "./now-playing";
import { coolingText, progressText } from "./progress";
import { Swipe } from "./touchpad";
import type { ButtonView, CardConfig, GroupView, HomeAssistant, RoomInfo, RoomView } from "./types";

const DOMAIN = "av_scenes";

const COMMAND_ICONS: Record<string, string> = {
  volume_up: "mdi:volume-plus",
  volume_down: "mdi:volume-minus",
  mute: "mdi:volume-off",
  channel_up: "mdi:chevron-up",
  channel_down: "mdi:chevron-down",
  play_pause: "mdi:play-pause",
  play: "mdi:play",
  pause: "mdi:pause",
  stop: "mdi:stop",
  next: "mdi:skip-next",
  previous: "mdi:skip-previous",
  up: "mdi:chevron-up",
  down: "mdi:chevron-down",
  left: "mdi:chevron-left",
  right: "mdi:chevron-right",
  back: "mdi:arrow-u-left-top",
  menu: "mdi:menu",
  home: "mdi:home-outline",
  info: "mdi:information-outline",
  guide: "mdi:television-guide",
  exit: "mdi:close",
  select_source: "mdi:apps",
};

const NAV_EXTRAS = ["back", "home", "menu", "info", "guide", "exit"];
const TRANSPORT = ["previous", "play_pause", "play", "pause", "stop", "next"];

/** Commands that repeat while the button is held. */
const REPEATING = new Set(["volume_up", "volume_down", "up", "down", "left", "right"]);
const REPEAT_DELAY = 400;
const REPEAT_INTERVAL = 200;
/** Wait before subscribing again after the integration refused (e.g. not loaded yet). */
const RETRY_DELAY = 30_000;

const STATE_ICONS: Record<string, string> = {
  idle: "mdi:power",
  starting: "mdi:timer-sand",
  active: "mdi:power",
  stopping: "mdi:timer-sand",
  error: "mdi:alert-circle-outline",
};

export class AvScenesRemoteCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    preview: { attribute: false },
    _config: { state: true },
    _view: { state: true },
    _loaded: { state: true },
    _subscribeError: { state: true },
    _volumeDraft: { state: true },
  };

  declare hass?: HomeAssistant;
  /**
   * Show this view instead of subscribing (the configuration panel). Buttons
   * send nothing then; they fire "preview-call" with the action they would call.
   */
  declare preview?: RoomView;
  declare _config?: CardConfig;
  declare _view: RoomView | null;
  declare _loaded: boolean;
  declare _subscribeError?: string;
  /** Slider position while it is being dragged (0–100). */
  declare _volumeDraft?: number;

  private _unsubscribe?: Promise<() => Promise<void>>;
  private _repeatTimer?: number;
  private _retryTimer?: number;
  /** Moves the playback position on while something plays. */
  private _tickTimer?: number;
  // The touch on the swipe area, from pointerdown until it is lifted
  private _swipe?: Swipe;
  // The key held down, until it is released or the press is cancelled
  private _press?: { command: string; extra: Record<string, unknown>; sent: boolean };

  constructor() {
    super();
    this._view = null;
    this._loaded = false;
  }

  // ------------------------------------------------------------------
  // Lovelace API
  // ------------------------------------------------------------------

  static getConfigElement(): HTMLElement {
    return document.createElement("av-scenes-remote-card-editor");
  }

  static async getStubConfig(hass: HomeAssistant): Promise<Partial<CardConfig>> {
    try {
      const rooms = await hass.callWS<RoomInfo[]>({ type: `${DOMAIN}/control/rooms` });
      return { room: rooms[0]?.room ?? "" };
    } catch {
      return { room: "" };
    }
  }

  setConfig(config: CardConfig): void {
    if (!config || typeof config.room !== "string") {
      throw new Error("room is required");
    }
    const changed =
      config.room !== this._config?.room || config.entry_id !== this._config?.entry_id;
    this._config = config;
    if (changed) {
      this._resubscribe();
    }
  }

  getCardSize(): number {
    return this._view?.remote ? 8 : 3;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  // ------------------------------------------------------------------
  // Subscription
  // ------------------------------------------------------------------

  connectedCallback(): void {
    super.connectedCallback();
    this._subscribe();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._pressEnd(false);
    window.clearInterval(this._tickTimer);
    this._tickTimer = undefined;
    this._unsubscribeNow();
  }

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has("preview") && this.preview) {
      this._config = { type: "custom:av-scenes-remote-card", room: this.preview.room };
      this._view = this.preview;
      this._loaded = true;
    }
  }

  protected updated(changed: PropertyValues): void {
    const now = this._nowPlaying();
    const ticking =
      (now?.playing === true && now.duration !== undefined) ||
      Boolean(this._view?.current?.until) ||
      Boolean(this._view?.cooling?.length);
    if (ticking && this._tickTimer === undefined) {
      this._tickTimer = window.setInterval(() => this.requestUpdate(), 1000);
    } else if (!ticking && this._tickTimer !== undefined) {
      window.clearInterval(this._tickTimer);
      this._tickTimer = undefined;
    }
    if (changed.has("hass") && !this._unsubscribe && this._retryTimer === undefined) {
      this._subscribe();
    }
  }

  private _subscribe(): void {
    if (this.preview || !this.hass || !this._config?.room || this._unsubscribe || !this.isConnected) {
      return;
    }
    const message: Record<string, unknown> = {
      type: `${DOMAIN}/control/subscribe`,
      room: this._config.room,
    };
    if (this._config.entry_id) {
      message.entry_id = this._config.entry_id;
    }
    const subscription = this.hass.connection.subscribeMessage<RoomView | null>((view) => {
      this._view = view;
      this._loaded = true;
      this._subscribeError = undefined;
    }, message);
    this._unsubscribe = subscription;
    subscription.catch((err: { message?: string }) => {
      if (this._unsubscribe !== subscription) {
        return; // a newer subscription replaced this one
      }
      this._subscribeError = err?.message ?? String(err);
      this._loaded = true;
      this._unsubscribe = undefined;
      // Not on every hass update, which would send a subscribe per state change
      this._retryTimer = window.setTimeout(() => {
        this._retryTimer = undefined;
        this._subscribe();
      }, RETRY_DELAY);
    });
  }

  private _unsubscribeNow(): void {
    window.clearTimeout(this._retryTimer);
    this._retryTimer = undefined;
    const subscription = this._unsubscribe;
    this._unsubscribe = undefined;
    subscription?.then((unsub) => unsub()).catch(() => undefined);
  }

  private _resubscribe(): void {
    this._unsubscribeNow();
    this._view = null;
    this._loaded = false;
    this._subscribe();
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  private _t(key: string, params?: Record<string, string>): string {
    return localize(this.hass?.language, key, params);
  }

  private _call(service: string, data: Record<string, unknown> = {}): void {
    if (!this.hass || !this._view) {
      return;
    }
    this._haptic();
    if (this.preview) {
      this.dispatchEvent(new CustomEvent("preview-call", { detail: { service, data } }));
      return;
    }
    this.hass
      .callService(DOMAIN, service, { room: this._view.room, ...data })
      .catch((err: { message?: string }) => this._toast(err?.message ?? String(err)));
  }

  private _send(command: string, extra: Record<string, unknown> = {}): void {
    this._call("send_command", { command, ...extra });
  }

  private _haptic(): void {
    this.dispatchEvent(
      new CustomEvent("haptic", { detail: "light", bubbles: true, composed: true }),
    );
  }

  private _toast(message: string): void {
    this.dispatchEvent(
      new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }),
    );
  }

  /**
   * A key sends on release, so a swipe that starts on it (scrolling the
   * dashboard) sends nothing: the browser cancels the pointer instead.
   * Held down, volume and arrow keys repeat.
   */
  private _pressStart(ev: PointerEvent, command: string, extra: Record<string, unknown> = {}): void {
    if (ev.button !== 0) {
      return;
    }
    this._pressEnd(false);
    const press = { command, extra, sent: false };
    this._press = press;
    if (!REPEATING.has(command)) {
      return;
    }
    this._repeatTimer = window.setTimeout(() => {
      press.sent = true;
      this._send(command, extra);
      this._repeatTimer = window.setInterval(() => this._send(command, extra), REPEAT_INTERVAL);
    }, REPEAT_DELAY);
  }

  private _pressEnd(send: boolean): void {
    const press = this._press;
    this._press = undefined;
    this._stopRepeat();
    if (send && press && !press.sent) {
      this._send(press.command, press.extra);
    }
  }

  private _stopRepeat(): void {
    if (this._repeatTimer !== undefined) {
      window.clearTimeout(this._repeatTimer);
      window.clearInterval(this._repeatTimer);
      this._repeatTimer = undefined;
    }
  }

  private _keySend(ev: KeyboardEvent, command: string, extra: Record<string, unknown> = {}): void {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      this._send(command, extra);
    }
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------

  protected render(): TemplateResult {
    if (!this._config?.room) {
      return html`<ha-card><div class="message">${this._t("no_room")}</div></ha-card>`;
    }
    if (!this._loaded) {
      return html`<ha-card><div class="message">${this._t("loading")}</div></ha-card>`;
    }
    const view = this._view;
    if (!view) {
      return html`<ha-card>
        <div class="message warning">
          ${this._subscribeError ?? this._t("not_found", { room: this._config.room })}
        </div>
      </ha-card>`;
    }
    return html`<ha-card>
      ${this._renderHeader(view)} ${this._renderStatus(view)} ${this._renderNowPlaying()}
      ${this._renderActivities(view)}
      ${view.remote ? this._renderRemote(view) : nothing}
    </ha-card>`;
  }

  private _renderHeader(view: RoomView): TemplateResult {
    const activity = view.activities.find((a) => a.id === view.activity);
    const on = view.state !== "idle";
    const status = activity
      ? `${activity.name} · ${this._t(`state.${view.state}`)}`
      : this._t(`state.${view.state}`);
    return html`<div class="header">
      <div class="title">
        <div class="name">${this._config?.name || view.name}</div>
        <div class="status state-${view.state}">${status}</div>
      </div>
      <button
        class="power ${on ? "on" : ""} state-${view.state}"
        title=${this._t("power")}
        aria-label=${this._t("power")}
        @click=${() => this._call("toggle_activity")}
      >
        <ha-icon .icon=${STATE_ICONS[view.state] ?? "mdi:power"}></ha-icon>
      </button>
    </div>`;
  }

  private _renderStatus(view: RoomView): TemplateResult | typeof nothing {
    const busy = view.state === "starting" || view.state === "stopping";
    const [done, total] = view.progress;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const doing = busy ? progressText(view.current, Date.now(), (key, params) => this._t(key, params)) : undefined;
    return html`
      ${busy
        ? html`<div class="progress" role="progressbar" aria-valuenow=${pct}>
            <div style="width: ${view.state === "starting" ? pct : 100}%"></div>
          </div>`
        : nothing}
      ${doing
        ? html`<div class="doing" aria-live="polite">
            <span class="doing-text">${doing.text}</span>
            ${doing.time ? html`<span class="doing-time">${doing.time}</span>` : nothing}
          </div>`
        : nothing}
      ${(view.cooling ?? []).map((cooling) => {
        const { text, time } = coolingText(cooling, Date.now(), (key, params) => this._t(key, params));
        return html`<div class="doing cooling">
          <span class="doing-text">${text}</span><span class="doing-time">${time}</span>
        </div>`;
      })}
      ${view.state === "error" && view.error
        ? html`<div class="message error">
            <ha-icon icon="mdi:alert-circle-outline"></ha-icon>${view.error}
          </div>`
        : nothing}
      ${view.warnings.length && view.state !== "idle"
        ? html`<details class="warnings">
            <summary>${this._t("warnings")} (${view.warnings.length})</summary>
            <ul>
              ${view.warnings.map((w) => html`<li>${w}</li>`)}
            </ul>
          </details>`
        : nothing}
    `;
  }

  /** What the media player of the running activity plays, if anything. */
  private _nowPlaying(): NowPlaying | undefined {
    const entityId = this._view?.remote?.media;
    return nowPlaying(entityId ? this.hass?.states[entityId] : undefined, Date.now());
  }

  private _renderNowPlaying(): TemplateResult | typeof nothing {
    const now = this._nowPlaying();
    if (!now) {
      return nothing;
    }
    const top = [now.app, now.playing ? undefined : this._t("now.paused")].filter(Boolean).join(" · ");
    return html`<div class="now">
      ${now.picture
        ? html`<img
            class="art"
            src=${now.picture}
            alt=""
            @error=${(ev: Event) => ((ev.target as HTMLElement).style.display = "none")}
          />`
        : nothing}
      <div class="meta">
        ${top ? html`<div class="now-top">${top}</div>` : nothing}
        <div class="now-title">${now.title}</div>
        ${now.subtitle ? html`<div class="now-sub">${now.subtitle}</div>` : nothing}
        ${now.duration !== undefined && now.position !== undefined
          ? html`<div class="now-progress" role="progressbar" aria-valuemin="0"
                aria-valuemax=${Math.round(now.duration)} aria-valuenow=${Math.round(now.position)}>
                <div style="width: ${(now.position / now.duration) * 100}%"></div>
              </div>
              <div class="now-time">
                <span>${clock(now.position)}</span><span>${clock(now.duration)}</span>
              </div>`
          : nothing}
      </div>
    </div>`;
  }

  private _renderActivities(view: RoomView): TemplateResult {
    return html`<div class="activities">
      ${view.activities.map((activity) => {
        const current = activity.id === view.activity;
        return html`<button
          class="chip ${current ? `current state-${view.state}` : ""}"
          aria-pressed=${current ? "true" : "false"}
          @click=${() => this._call("start_activity", { activity: activity.id })}
        >
          <ha-icon .icon=${activity.icon ?? "mdi:play-circle-outline"}></ha-icon>
          <span>${activity.name}</span>
        </button>`;
      })}
    </div>`;
  }

  private _renderRemote(view: RoomView): TemplateResult {
    const { groups, buttons } = view.remote!;
    const nav = groups.navigation;
    const navExtras = nav ? NAV_EXTRAS.filter((c) => nav.commands.includes(c)) : [];
    let transport = groups.transport
      ? TRANSPORT.filter((c) => groups.transport!.commands.includes(c))
      : [];
    if (transport.includes("play_pause")) {
      transport = transport.filter((c) => c !== "play" && c !== "pause");
    }
    return html`<div class="remote">
      ${groups.volume || nav || groups.channels
        ? html`<div class="main ${nav ? "" : "no-nav"}">
            ${groups.volume ? this._renderVolumeRocker(groups.volume) : nav ? html`<div></div>` : nothing}
            ${nav ? (nav.touchpad ? this._renderTouchpad(nav) : this._renderDpad(nav)) : nothing}
            ${groups.channels ? this._renderChannelRocker(groups.channels) : nav ? html`<div></div>` : nothing}
          </div>`
        : nothing}
      ${groups.volume?.commands.includes("volume_set") ? this._renderSlider(groups.volume) : nothing}
      ${navExtras.length ? html`<div class="row">${navExtras.map((c) => this._key(c))}</div>` : nothing}
      ${transport.length ? html`<div class="row">${transport.map((c) => this._key(c))}</div>` : nothing}
      ${buttons.length
        ? html`<div class="buttons">${buttons.map((b) => this._customButton(b))}</div>`
        : nothing}
    </div>`;
  }

  private _key(command: string, cls = "key", content?: TemplateResult | string): TemplateResult {
    return html`<button
      class=${cls}
      title=${this._t(`command.${command}`)}
      aria-label=${this._t(`command.${command}`)}
      @pointerdown=${(ev: PointerEvent) => this._pressStart(ev, command)}
      @pointerup=${() => this._pressEnd(true)}
      @pointerleave=${() => this._pressEnd(false)}
      @pointercancel=${() => this._pressEnd(false)}
      @keydown=${(ev: KeyboardEvent) => this._keySend(ev, command)}
      @contextmenu=${(ev: Event) => ev.preventDefault()}
    >
      ${content ?? html`<ha-icon .icon=${COMMAND_ICONS[command] ?? "mdi:circle-small"}></ha-icon>`}
    </button>`;
  }

  private _renderVolumeRocker(group: GroupView): TemplateResult {
    const muted = this._volumeState(group).muted;
    return html`<div class="rocker">
      ${group.commands.includes("volume_up") ? this._key("volume_up") : html`<span></span>`}
      ${group.commands.includes("mute")
        ? this._key(
            "mute",
            `key label ${muted ? "active" : ""}`,
            html`<ha-icon .icon=${muted ? "mdi:volume-off" : "mdi:volume-high"}></ha-icon>`,
          )
        : html`<span class="label">VOL</span>`}
      ${group.commands.includes("volume_down") ? this._key("volume_down") : html`<span></span>`}
    </div>`;
  }

  private _renderChannelRocker(group: GroupView): TemplateResult {
    return html`<div class="rocker">
      ${group.commands.includes("channel_up") ? this._key("channel_up") : html`<span></span>`}
      <span class="label">CH</span>
      ${group.commands.includes("channel_down") ? this._key("channel_down") : html`<span></span>`}
    </div>`;
  }

  private _renderDpad(group: GroupView): TemplateResult {
    const has = (c: string) => group.commands.includes(c);
    const cell = (c: string, cls: string) =>
      has(c) ? this._key(c, `key ${cls}`, c === "ok" ? "OK" : undefined) : html`<span></span>`;
    return html`<div class="dpad">
      <span></span>${cell("up", "up")}<span></span>
      ${cell("left", "left")}${cell("ok", "ok")}${cell("right", "right")}
      <span></span>${cell("down", "down")}<span></span>
    </div>`;
  }

  /** Swipe area instead of the arrow keys, for an Apple TV and the like. */
  private _renderTouchpad(group: GroupView): TemplateResult {
    const has = (command: string) => group.commands.includes(command);
    const keys: Record<string, string> = {
      ArrowUp: "up",
      ArrowDown: "down",
      ArrowLeft: "left",
      ArrowRight: "right",
      Enter: "ok",
      " ": "ok",
    };
    return html`<div
      class="touchpad"
      role="group"
      tabindex="0"
      aria-label=${this._t("touchpad")}
      title=${this._t("touchpad")}
      @pointerdown=${(ev: PointerEvent) => {
        if (ev.button !== 0) {
          return;
        }
        (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
        this._swipe = new Swipe();
        this._swipe.start(ev.clientX, ev.clientY, ev.timeStamp);
      }}
      @pointermove=${(ev: PointerEvent) => {
        for (const key of this._swipe?.move(ev.clientX, ev.clientY) ?? []) {
          if (has(key)) this._send(key);
        }
      }}
      @pointerup=${(ev: PointerEvent) => {
        const tap = this._swipe?.end(ev.clientX, ev.clientY, ev.timeStamp);
        this._swipe = undefined;
        if (tap && has("ok")) this._send("ok");
      }}
      @pointercancel=${() => (this._swipe = undefined)}
      @keydown=${(ev: KeyboardEvent) => {
        const key = keys[ev.key];
        if (key && has(key)) {
          ev.preventDefault();
          this._send(key);
        }
      }}
      @contextmenu=${(ev: Event) => ev.preventDefault()}
    >
      <span class="touchpad-hint">${this._t("touchpad.hint")}</span>
    </div>`;
  }

  private _volumeState(group: GroupView): { level?: number; muted: boolean } {
    const state = group.entity_id ? this.hass?.states[group.entity_id] : undefined;
    const level = state?.attributes.volume_level;
    return {
      level: typeof level === "number" ? level : undefined,
      muted: state?.attributes.is_volume_muted === true,
    };
  }

  private _renderSlider(group: GroupView): TemplateResult {
    const { level } = this._volumeState(group);
    const value = this._volumeDraft ?? (level !== undefined ? Math.round(level * 100) : 0);
    return html`<div class="slider">
      <ha-icon icon="mdi:volume-medium"></ha-icon>
      <input
        type="range"
        min="0"
        max="100"
        step="1"
        .value=${String(value)}
        ?disabled=${level === undefined}
        aria-label=${this._t("volume")}
        @input=${(ev: Event) => {
          this._volumeDraft = Number((ev.target as HTMLInputElement).value);
        }}
        @change=${(ev: Event) => {
          const pct = Number((ev.target as HTMLInputElement).value);
          this._volumeDraft = undefined;
          this._send("volume_set", { value: pct / 100 });
        }}
      />
      <span class="value">${level !== undefined || this._volumeDraft !== undefined ? value : "–"}</span>
    </div>`;
  }

  private _customButton(button: ButtonView): TemplateResult {
    const label = button.name ?? this._t(`command.${button.command}`);
    const extra: Record<string, unknown> = {};
    if (button.device) extra.device = button.device;
    if (button.value !== null && button.value !== undefined) extra.value = button.value;
    return html`<button
      class="custom"
      title=${label}
      @pointerdown=${(ev: PointerEvent) => this._pressStart(ev, button.command, extra)}
      @pointerup=${() => this._pressEnd(true)}
      @pointerleave=${() => this._pressEnd(false)}
      @pointercancel=${() => this._pressEnd(false)}
      @keydown=${(ev: KeyboardEvent) => this._keySend(ev, button.command, extra)}
    >
      ${button.icon || COMMAND_ICONS[button.command]
        ? html`<ha-icon .icon=${button.icon ?? COMMAND_ICONS[button.command]}></ha-icon>`
        : nothing}
      <span>${label}</span>
    </button>`;
  }

  static styles = css`
    :host {
      --avs-key-bg: var(--secondary-background-color, #f0f0f0);
      --avs-key-color: var(--primary-text-color, #212121);
      --avs-accent: var(--primary-color, #03a9f4);
      --avs-radius: 12px;
    }
    ha-card {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    button {
      font: inherit;
      color: inherit;
      border: none;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      touch-action: manipulation;
      user-select: none;
      -webkit-user-select: none;
    }
    button:focus-visible {
      outline: 2px solid var(--avs-accent);
      outline-offset: 2px;
    }
    .header {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .title {
      flex: 1;
      min-width: 0;
    }
    .name {
      font-size: 1.2em;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .status {
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    .status.state-error {
      color: var(--error-color, #db4437);
    }
    .power {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      background: var(--avs-key-bg);
      display: grid;
      place-items: center;
      flex: none;
    }
    .power.on {
      background: var(--avs-accent);
      color: var(--text-primary-color, #fff);
    }
    .power.state-error {
      background: var(--error-color, #db4437);
    }
    .doing {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-top: -6px;
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    .doing.cooling {
      margin-top: 0;
    }
    .doing-text {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .doing-time {
      flex: none;
      font-variant-numeric: tabular-nums;
    }
    .now {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .now .art {
      width: 64px;
      height: 64px;
      flex: none;
      border-radius: 8px;
      object-fit: cover;
      background: var(--avs-key-bg);
    }
    .now .meta {
      flex: 1;
      min-width: 0;
    }
    .now-top,
    .now-sub,
    .now-time {
      color: var(--secondary-text-color);
      font-size: 0.85em;
    }
    .now-top,
    .now-title,
    .now-sub {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .now-title {
      font-weight: 500;
    }
    .now-progress {
      height: 3px;
      margin-top: 6px;
      border-radius: 2px;
      background: var(--divider-color, rgba(0, 0, 0, 0.12));
      overflow: hidden;
    }
    .now-progress div {
      height: 100%;
      background: var(--avs-accent);
    }
    .now-time {
      display: flex;
      justify-content: space-between;
      font-variant-numeric: tabular-nums;
      margin-top: 2px;
    }
    .progress {
      height: 4px;
      border-radius: 2px;
      background: var(--divider-color, rgba(0, 0, 0, 0.12));
      overflow: hidden;
    }
    .progress div {
      height: 100%;
      background: var(--avs-accent);
      transition: width 0.3s ease;
    }
    .message {
      color: var(--secondary-text-color);
    }
    .message.error,
    .message.warning {
      color: var(--error-color, #db4437);
      display: flex;
      gap: 8px;
      align-items: flex-start;
      overflow-wrap: anywhere;
    }
    .warnings {
      font-size: 0.9em;
      color: var(--warning-color, #ffa600);
    }
    .warnings ul {
      margin: 4px 0 0;
      padding-left: 20px;
      color: var(--secondary-text-color);
      overflow-wrap: anywhere;
    }
    .activities {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 18px;
      background: var(--avs-key-bg);
      --mdc-icon-size: 20px;
    }
    .chip.current {
      background: var(--avs-accent);
      color: var(--text-primary-color, #fff);
    }
    .chip.current.state-starting,
    .chip.current.state-stopping {
      animation: pulse 1.2s ease-in-out infinite;
    }
    .chip.current.state-error {
      background: var(--error-color, #db4437);
    }
    @keyframes pulse {
      50% {
        opacity: 0.6;
      }
    }
    .remote {
      display: flex;
      flex-direction: column;
      gap: 12px;
      border-top: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
      padding-top: 12px;
    }
    .main {
      display: grid;
      grid-template-columns: 56px 1fr 56px;
      align-items: center;
      gap: 12px;
    }
    .main.no-nav {
      display: flex;
      justify-content: center;
      gap: 64px;
    }
    .main.no-nav .rocker {
      width: 56px;
    }
    .rocker {
      display: grid;
      grid-template-rows: 56px 40px 56px;
      background: var(--avs-key-bg);
      border-radius: 28px;
      overflow: hidden;
    }
    .rocker .key {
      background: none;
      border-radius: 0;
      width: 100%;
      height: 100%;
    }
    .rocker .label {
      display: grid;
      place-items: center;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .rocker .key.label.active {
      color: var(--error-color, #db4437);
    }
    .key {
      display: grid;
      place-items: center;
      height: 48px;
      min-width: 48px;
      border-radius: var(--avs-radius);
      background: var(--avs-key-bg);
      color: var(--avs-key-color);
    }
    .key:active,
    .custom:active,
    .chip:active,
    .power:active {
      filter: brightness(0.85);
    }
    .touchpad {
      display: grid;
      place-items: end center;
      width: 100%;
      max-width: 220px;
      height: 164px;
      justify-self: center;
      border-radius: 20px;
      background: var(--avs-key-bg);
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
      cursor: pointer;
    }
    .touchpad:active {
      filter: brightness(0.94);
    }
    .touchpad:focus-visible {
      outline: 2px solid var(--avs-accent);
      outline-offset: 2px;
    }
    .touchpad-hint {
      padding-bottom: 10px;
      font-size: 0.75em;
      color: var(--secondary-text-color);
      pointer-events: none;
    }
    .dpad {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      grid-template-rows: repeat(3, 52px);
      gap: 4px;
      max-width: 220px;
      width: 100%;
      justify-self: center;
    }
    .dpad .key {
      height: 100%;
    }
    .dpad .ok {
      border-radius: 50%;
      font-weight: 600;
      background: var(--avs-accent);
      color: var(--text-primary-color, #fff);
    }
    .row {
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 8px;
    }
    .row .key {
      flex: 1 1 0;
      max-width: 72px;
    }
    .slider {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--secondary-text-color);
    }
    .slider input {
      flex: 1;
      accent-color: var(--avs-accent);
      min-width: 0;
    }
    .slider .value {
      width: 3ch;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .buttons {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
      gap: 8px;
    }
    .custom {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      min-height: 44px;
      padding: 6px 10px;
      border-radius: var(--avs-radius);
      background: var(--avs-key-bg);
      --mdc-icon-size: 20px;
    }
  `;
}

if (!customElements.get("av-scenes-remote-card")) {
  customElements.define("av-scenes-remote-card", AvScenesRemoteCard);
}

/**
 * The room an entity belongs to: every entity of AV Scenes sits on the
 * room's device, whose identifier is ("av_scenes", room id).
 */
export function roomOfEntity(hass: HomeAssistant, entityId: string): string | null {
  const deviceId = hass.entities?.[entityId]?.device_id;
  const device = deviceId ? hass.devices?.[deviceId] : undefined;
  const identifier = device?.identifiers?.find(([domain]) => domain === DOMAIN);
  return identifier ? identifier[1] : null;
}

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
  /** Card picker (HA 2026.6+): suggest the card for the entities of a room. */
  getEntitySuggestion?: (
    hass: HomeAssistant,
    entityId: string,
  ) => { label?: string; config: Record<string, unknown> } | null;
}

const win = window as unknown as { customCards?: CustomCardEntry[] };
win.customCards = win.customCards ?? [];
if (!win.customCards.some((card) => card.type === "av-scenes-remote-card")) {
  win.customCards.push({
    type: "av-scenes-remote-card",
    name: "AV Scenes Remote",
    description: "Remote control for an AV Scenes room",
    preview: true,
    documentationURL: "https://github.com/mkshb/hass-av-scenes#the-card",
    getEntitySuggestion: (hass, entityId) => {
      const room = roomOfEntity(hass, entityId);
      return room ? { config: { type: "custom:av-scenes-remote-card", room } } : null;
    },
  });
}
