/**
 * The guide at the top of the panel: how to set up a room, the terms used
 * in the forms and an example. Collapsed by default; the browser remembers
 * whether it was open.
 */
import { LitElement, css, html, type TemplateResult } from "lit";

const DOCS = "https://github.com/mkshb/hass-av-scenes#readme";
const STORAGE_KEY = "av-scenes-guide-open";

interface Guide {
  title: string;
  steps_title: string;
  steps: TemplateResult[];
  terms_title: string;
  terms: [string, string][];
  example_title: string;
  example: TemplateResult[];
  docs: TemplateResult;
}

const GUIDES: Record<string, Guide> = {
  en: {
    title: "Guide",
    steps_title: "How it works",
    steps: [
      html`<b>Add the devices</b> of the room under <i>Devices</i>: pick each device's entity. If it hangs on a
        switchable outlet, enter it under <i>Power</i>. If it loses its connection without power (Apple TV), use
        the recommended button under <i>Connection check</i>.`,
      html`<b>Put together activities</b> under <i>Activities</i>: choose the devices in the order they are
        switched on, and under <i>Start sequence</i> for example the TV's input. Quick-select buttons start apps.`,
      html`<b>Save and add the card:</b> save at the top right. On a dashboard, add a card, search for
        <i>AV Scenes Remote</i> and choose the room.`,
    ],
    terms_title: "Terms",
    terms: [
      ["Outlet", "Switch that powers the device. Switched on first and off last; outlets shared by several devices stay on while one of them is needed."],
      ["Boot time", "Wait after the outlet came on, before the device is switched on. Only when the outlet was off."],
      ["Waiting times", "After switching on: until the device accepts commands. After switching off: cool-down, e.g. for a projector lamp."],
      ["Connection check", "Waits until the device is reachable in Home Assistant, at the start and before remote buttons; can reload its integration until it connects."],
      ["Start sequence", "Settings once all devices are on: input, volume, sound mode, any action."],
      ["Remote control", "Which device gets volume, channels, playback and arrow keys. Automatic: volume to the first media player, the rest to the last."],
      ["Quick select", "Buttons that switch a media player to a source, on an Apple TV to an app."],
      ["Settings in the card", "Source, sound mode and entities of the devices such as tone controls, changeable in the card while the activity runs; automatic or chosen with favourites."],
    ],
    example_title: "Example: TV and Apple TV",
    example: [
      html`Device <i>TV</i>: entity <code>media_player.tv</code>, outlet <code>switch.tv_outlet</code>, boot time
        15 s, wait after switching on 10 s.`,
      html`Device <i>Apple TV</i>: entity <code>media_player.apple_tv</code>, under <i>Connection check</i> the
        button <i>Use remote.apple_tv for the connection check and the arrow keys</i>.`,
      html`Activity <i>Apple TV</i>: devices TV, then Apple TV; start sequence <i>Set source</i> on the TV to its
        HDMI input; quick select Apple TV with Netflix.`,
      html`Save, add the card, start the activity.`,
    ],
    docs: html`All options and the YAML reference: <a href=${DOCS} target="_blank" rel="noreferrer">documentation on GitHub</a>.`,
  },
  de: {
    title: "Anleitung",
    steps_title: "So geht's",
    steps: [
      html`<b>Geräte anlegen</b> unter <i>Geräte</i>: Für jedes Gerät die Entität wählen. Hängt es an einer
        schaltbaren Steckdose, diese unter <i>Strom</i> eintragen. Verliert es ohne Strom die Verbindung (Apple
        TV), unter <i>Verbindung prüfen</i> den empfohlenen Knopf nutzen.`,
      html`<b>Aktivitäten zusammenstellen</b> unter <i>Aktivitäten</i>: die Geräte in Einschaltreihenfolge wählen,
        unter <i>Ablauf beim Start</i> zum Beispiel den Eingang des TV. Schnellwahl-Tasten starten Apps.`,
      html`<b>Speichern und Card einfügen:</b> oben rechts speichern. Im Dashboard eine Karte hinzufügen,
        <i>AV Scenes Remote</i> suchen und den Raum wählen.`,
    ],
    terms_title: "Begriffe",
    terms: [
      ["Steckdose", "Schalter, an dem das Gerät hängt. Wird zuerst ein- und zuletzt ausgeschaltet; gemeinsame Steckdosen mehrerer Geräte bleiben an, solange eines davon gebraucht wird."],
      ["Startzeit", "Wartezeit nach dem Einschalten der Steckdose, bevor das Gerät eingeschaltet wird. Nur wenn die Steckdose aus war."],
      ["Wartezeiten", "Nach dem Einschalten: bis das Gerät Befehle annimmt. Nach dem Ausschalten: Abkühlzeit, z. B. für eine Beamer-Lampe."],
      ["Verbindung prüfen", "Wartet, bis das Gerät in Home Assistant erreichbar ist, beim Start und vor Tasten der Fernbedienung; kann seine Integration neu laden, bis sie verbunden ist."],
      ["Ablauf beim Start", "Einstellungen, sobald alle Geräte an sind: Eingang, Lautstärke, Klangmodus, beliebige Aktion."],
      ["Fernbedienung", "Welches Gerät Lautstärke, Sender, Wiedergabe und Pfeiltasten bekommt. Automatisch: Lautstärke an den ersten Mediaplayer, der Rest an den letzten."],
      ["Schnellwahl", "Tasten, die einen Mediaplayer auf eine Quelle schalten, beim Apple TV auf eine App."],
      ["Einstellungen in der Karte", "Quelle, Klangmodus und Entitäten der Geräte wie Klangregler, in der Karte änderbar, während die Aktivität läuft; automatisch oder ausgewählt mit Favoriten."],
    ],
    example_title: "Beispiel: TV und Apple TV",
    example: [
      html`Gerät <i>TV</i>: Entität <code>media_player.tv</code>, Steckdose <code>switch.steckdose_tv</code>,
        Startzeit 15 s, Warten nach Einschalten 10 s.`,
      html`Gerät <i>Apple TV</i>: Entität <code>media_player.apple_tv</code>, unter <i>Verbindung prüfen</i> der
        Knopf <i>remote.apple_tv für Verbindungsprüfung und Pfeiltasten nutzen</i>.`,
      html`Aktivität <i>Apple TV</i>: Geräte TV, dann Apple TV; Ablauf beim Start <i>Quelle wählen</i> am TV auf
        den HDMI-Eingang; Schnellwahl Apple TV mit Netflix.`,
      html`Speichern, Card einfügen, Aktivität starten.`,
    ],
    docs: html`Alle Optionen und die YAML-Referenz: <a href=${DOCS} target="_blank" rel="noreferrer">Dokumentation auf GitHub</a>.`,
  },
};

function readOpen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeOpen(open: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  } catch {
    // Storage blocked: the guide just starts collapsed again
  }
}

export class AvScenesGuide extends LitElement {
  static properties = { language: {} };

  declare language?: string;

  protected render(): TemplateResult {
    const lang = (this.language ?? "en").split("-")[0];
    const g = GUIDES[lang] ?? GUIDES.en;
    return html`<details
      ?open=${readOpen()}
      @toggle=${(ev: Event) => writeOpen((ev.target as HTMLDetailsElement).open)}
    >
      <summary><ha-icon icon="mdi:help-circle-outline"></ha-icon><span>${g.title}</span></summary>
      <div class="body">
        <h3>${g.steps_title}</h3>
        <ol>
          ${g.steps.map((step) => html`<li>${step}</li>`)}
        </ol>
        <h3>${g.terms_title}</h3>
        <dl>
          ${g.terms.map(([term, text]) => html`<dt>${term}</dt><dd>${text}</dd>`)}
        </dl>
        <h3>${g.example_title}</h3>
        <ol>
          ${g.example.map((step) => html`<li>${step}</li>`)}
        </ol>
        <p>${g.docs}</p>
      </div>
    </details>`;
  }

  static styles = css`
    :host {
      display: block;
      margin-bottom: 16px;
    }
    details {
      border: 1px solid var(--divider-color);
      border-radius: 12px;
      background: var(--card-background-color);
    }
    summary {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      cursor: pointer;
      font-weight: 500;
      color: var(--primary-color);
    }
    .body {
      padding: 0 16px 16px;
      line-height: 1.5;
    }
    h3 {
      font-size: 1em;
      font-weight: 500;
      margin: 12px 0 4px;
    }
    ol {
      margin: 0;
      padding-left: 22px;
    }
    li {
      margin-bottom: 6px;
    }
    dl {
      margin: 0;
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 4px 16px;
    }
    dt {
      font-weight: 500;
    }
    dd {
      margin: 0;
      color: var(--secondary-text-color);
    }
    @media (max-width: 600px) {
      dl {
        grid-template-columns: 1fr;
      }
      dd {
        margin-bottom: 6px;
      }
    }
    code {
      font-size: 0.9em;
      overflow-wrap: anywhere;
    }
    a {
      color: var(--primary-color);
    }
  `;
}

if (!customElements.get("av-scenes-guide")) {
  customElements.define("av-scenes-guide", AvScenesGuide);
}
