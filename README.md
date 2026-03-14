# AV Scenes - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/mkshb/ha_av_scenes.svg)](https://github.com/mkshb/ha_av_scenes/releases)
[![License](https://img.shields.io/github/license/mkshb/ha_av_scenes.svg)](LICENSE)

Home Assistant Integration für aktivitätsbasierte Steuerung von AV-Geräten. Eine Open-Source-Alternative zu Logitech Harmony und Roomie Remote.

[English](#english) | [Deutsch](#deutsch)

---

## Deutsch

### Überblick

AV Scenes ermöglicht es, mehrere Geräte (Receiver, Beamer, TV, Lichter, Steckdosen, Rollläden) über vorkonfigurierte Aktivitäten zu steuern — ohne YAML. Aktivitäten werden Schritt für Schritt ausgeführt und können dabei beliebige Home Assistant Entities und Actions einbinden.

### Features

| Feature | Beschreibung |
|---------|-------------|
| Multiroom | Unabhängige Aktivitätsverwaltung pro Raum |
| 10 Schritt-Typen | Gerät ein/aus, Quelle, Lautstärke, Soundmodus, Helligkeit, Farbtemperatur, Position, Neigung, Delay, beliebige HA-Action |
| Intelligenter Aktivitätswechsel | Geräte, die in der neuen Aktivität nicht mehr benötigt werden, werden automatisch abgeschaltet |
| Flexible Delays | Konfigurierbare Wartezeit (0–60 s) nach jedem Schritt |
| Race-Condition-Schutz | Parallele Aufrufe für denselben Raum werden serialisiert |
| Sensor & Switch Entities | Vollständige Transparenz in Lovelace |
| UI-Konfiguration | Keine YAML-Kenntnisse erforderlich |
| Persistenz | Konfiguration überlebt HA-Neustarts |
| Zweisprachig | Vollständige deutsche und englische Oberfläche |

### Unterstützte Entity-Typen

| Typ | Domain | Steuerung |
|-----|--------|-----------|
| AV-Receiver, Beamer, TV, Media Player | `media_player.*` | Ein/Aus, Eingangsquelle, Lautstärke, Soundmodus |
| Lichter | `light.*` | Ein/Aus, Helligkeit, Farbtemperatur, Übergangszeit |
| Steckdosen / Schalter | `switch.*` | Ein/Aus |
| Rollläden | `cover.*` | Öffnen/Schließen, Position, Neigung |

### Installation

#### HACS (Empfohlen)

1. HACS in Home Assistant öffnen
2. "Integrationen" → drei Punkte oben rechts → "Benutzerdefinierte Repositories"
3. Repository hinzufügen:
   - **Repository:** `https://github.com/mkshb/ha_av_scenes`
   - **Kategorie:** Integration
4. "AV Scenes" in der Liste suchen und auf "Herunterladen" klicken
5. Home Assistant neu starten

#### Manuell

1. Neueste Version von [Releases](https://github.com/mkshb/ha_av_scenes/releases) herunterladen
2. Ordner `custom_components/av_scenes` in `config/custom_components/` kopieren
3. Home Assistant neu starten

### Einrichtung

1. **Einstellungen** → **Geräte & Dienste** → **+ Integration hinzufügen**
2. "AV Scenes" suchen und auswählen
3. Auf **Konfigurieren** klicken, um Räume und Aktivitäten einzurichten

#### Raum anlegen

1. Einen bestehenden Home Assistant Bereich auswählen **oder** einen eigenen Raumnamen vergeben
2. Bestätigen — der Raum erscheint sofort in der Liste

#### Aktivität erstellen

1. Raum auswählen → **Neue Aktivität hinzufügen**
2. Namen vergeben (z. B. „Film schauen")
3. Schritte hinzufügen — der Assistent führt durch die Konfiguration:

| Schritt-Typ | Gerät | Konfigurierbare Parameter |
|-------------|-------|--------------------------|
| **Turn on device** | Alle | — |
| **Set input source** | `media_player` | Eingangsquelle aus der Geräteliste |
| **Set volume** | `media_player` | Lautstärke 0–100 % |
| **Set sound mode** | `media_player` | Soundmodus aus der Geräteliste |
| **Set brightness/color** | `light` | Helligkeit 0–100 %, Farbtemperatur, Übergangszeit |
| **Set color temperature** | `light` | Farbtemperatur 153–500 Mired |
| **Set position** | `cover` | Position 0–100 % |
| **Set tilt** | `cover` | Neigung 0–100 % |
| **Call action** | — | HA-Service (Format: `domain.service`), optionale JSON-Daten |
| **Wait/Delay** | — | Wartezeit 1–60 Sekunden |

Jeder Schritt (außer Delay) kann zusätzlich eine Wartezeit `delay_after` bekommen, die **nach** dem Schritt abgewartet wird.

4. Optional: Schritte nachträglich **bearbeiten**, **löschen** oder **umsortieren**
5. Optional: Aktivitäten **kopieren** oder **umbenennen**
6. **Aktivität abschließen** — die Konfiguration wird sofort gespeichert

### Verwendung

#### Szenen

Für jede Aktivität wird automatisch eine HA-Szene erstellt:

```yaml
service: scene.turn_on
target:
  entity_id: scene.wohnzimmer_film_schauen
```

#### Services

```yaml
# Aktivität starten
service: av_scenes.start_activity
data:
  room: wohnzimmer
  activity: film_schauen

# Aktivität stoppen (alle Geräte ausschalten)
service: av_scenes.stop_activity
data:
  room: wohnzimmer

# Konfiguration neu laden
service: av_scenes.reload
```

> Die `room`-ID entspricht dem internen Raum-Bezeichner, der beim Anlegen des Raums vergeben wurde (kleingeschrieben, Leerzeichen als `_`).

#### Switch Entity

Jeder Raum erhält einen Switch, der anzeigt ob gerade eine Aktivität läuft:

```yaml
# Ist eine Aktivität aktiv?
{{ is_state('switch.wohnzimmer_activity', 'on') }}

# Welche Aktivität läuft gerade?
{{ state_attr('switch.wohnzimmer_activity', 'current_activity') }}

# Alle verfügbaren Aktivitäten
{{ state_attr('switch.wohnzimmer_activity', 'available_activities') }}

# Aktivität stoppen
service: switch.turn_off
target:
  entity_id: switch.wohnzimmer_activity
```

#### Sensor Entity

Jeder Raum erhält einen Konfigurations-Sensor:

```yaml
# Aktueller Status (idle / starting / active / stopping)
{{ states('sensor.wohnzimmer_configuration') }}

# Alle Aktivitätsnamen
{{ state_attr('sensor.wohnzimmer_configuration', 'activity_names') }}

# Anzahl der Aktivitäten
{{ state_attr('sensor.wohnzimmer_configuration', 'total_activities') }}
```

**Sensor-Attribute:**

| Attribut | Beschreibung |
|----------|-------------|
| `room_id` | Interne Raum-ID |
| `room_name` | Anzeigename des Raums |
| `total_activities` | Anzahl konfigurierter Aktivitäten |
| `activity_names` | Liste aller Aktivitätsnamen |
| `activities` | Vollständige Details inkl. Schritte und Einstellungen |
| `current_activity` | Name der aktiven Aktivität oder `null` |
| `status` | `idle`, `starting`, `active` oder `stopping` |

### Beispielszenarien

#### Filmabend

Schritte:

1. Receiver einschalten (`delay_after: 3s`)
2. Beamer einschalten (`delay_after: 10s`)
3. Blu-ray Player einschalten (`delay_after: 2s`)
4. Receiver Eingang auf BD/DVD setzen (`delay_after: 1s`)
5. Receiver Lautstärke auf 65 % setzen
6. Rollladen auf 0 % (geschlossen) setzen
7. Licht auf 5 % Helligkeit dimmen

#### Intelligenter Aktivitätswechsel: Apple TV → Sonos

**Laufende Aktivität „Apple TV"** nutzt: Beamer, Receiver, Apple TV

**Neue Aktivität „Sonos"** nutzt: Receiver, Sonos

Was AV Scenes automatisch macht:
- Beamer wird **ausgeschaltet** (nicht mehr benötigt)
- Apple TV wird **ausgeschaltet** (nicht mehr benötigt)
- Receiver bleibt **an** — nur Eingang und Lautstärke werden angepasst
- Sonos wird **eingeschaltet**

Ergebnis: Wechsel in 2–3 Sekunden statt 20–30 Sekunden.

#### Abhängige Geräte (Steckdose vor TV)

Wenn ein TV an einer schaltbaren Steckdose hängt, muss die Steckdose zuerst an sein:

1. Steckdose einschalten (`delay_after: 5s`) — TV hat jetzt Strom
2. Rollladen auf 60 % setzen (`delay_after: 1s`)
3. Licht auf 8 % dimmen (`delay_after: 1s`)
4. TV einschalten (`delay_after: 3s`) — bootet jetzt korrekt
5. TV Eingang auf HDMI 1 setzen (`delay_after: 1s`)
6. Apple TV einschalten

### Lovelace Beispiele

#### Aktivitäts-Karte

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Wohnzimmer
    entities:
      - entity: switch.wohnzimmer_activity
        name: Status
      - type: section
        label: Aktivitäten starten
      - entity: scene.wohnzimmer_film_schauen
        name: Film schauen
      - entity: scene.wohnzimmer_musik_hoeren
        name: Musik hören
      - entity: scene.wohnzimmer_gaming
        name: Gaming
```

#### Markdown-Karte mit Aktivitätsliste

```yaml
type: markdown
content: |
  ## Wohnzimmer — {{ states('sensor.wohnzimmer_configuration') }}
  **Aktivitäten ({{ state_attr('sensor.wohnzimmer_configuration', 'total_activities') }}):**
  {% for a in state_attr('sensor.wohnzimmer_configuration', 'activity_names') %}
  - {{ a }}
  {% endfor %}
```

### Automatisierung

```yaml
automation:
  - alias: "Filmabend um 20 Uhr"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.jemand_zuhause
        state: "on"
    action:
      - service: av_scenes.start_activity
        data:
          room: wohnzimmer
          activity: film_schauen
```

### Bekannte Einschränkungen

- Eingangsquellen-Auswahl benötigt das `source_list` Attribut am Gerät
- Soundmodus-Auswahl benötigt das `sound_mode_list` Attribut am Gerät
- Lautstärkeregelung benötigt den `media_player.volume_set` Service
- Rollläden mit Neigung benötigen den `cover.set_cover_tilt_position` Service

### Beitragen

1. Repository forken
2. Feature Branch erstellen: `git checkout -b feature/mein-feature`
3. Änderungen committen: `git commit -m 'Mein Feature'`
4. Branch pushen: `git push origin feature/mein-feature`
5. Pull Request öffnen

### Lizenz & Support

- Lizenz: [MIT](LICENSE)
- Bugs & Feature Requests: [GitHub Issues](https://github.com/mkshb/ha_av_scenes/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

---

## English

### Overview

AV Scenes lets you control multiple devices (receivers, projectors, TVs, lights, switches, covers) through pre-configured activities — without any YAML. Activities execute step by step and can integrate any Home Assistant entity or action.

### Features

| Feature | Description |
|---------|-------------|
| Multi-room | Independent activity management per room |
| 10 step types | Power on/off, source, volume, sound mode, brightness, color temp, position, tilt, delay, any HA action |
| Smart switching | Devices no longer needed in the new activity are turned off automatically |
| Flexible delays | Configurable wait time (0–60 s) after each step |
| Race condition protection | Concurrent calls for the same room are serialized |
| Sensor & switch entities | Full transparency in Lovelace |
| UI configuration | No YAML knowledge required |
| Persistence | Configuration survives HA restarts |
| Bilingual | Complete German and English UI |

### Supported Entity Types

| Type | Domain | Control |
|------|--------|---------|
| AV Receiver, Projector, TV, Media Player | `media_player.*` | On/off, input source, volume, sound mode |
| Lights | `light.*` | On/off, brightness, color temperature, transition |
| Outlets / Switches | `switch.*` | On/off |
| Covers | `cover.*` | Open/close, position, tilt |

### Installation

#### HACS (Recommended)

1. Open HACS in Home Assistant
2. "Integrations" → three dots top right → "Custom repositories"
3. Add repository:
   - **Repository:** `https://github.com/mkshb/ha_av_scenes`
   - **Category:** Integration
4. Find "AV Scenes" in the list and click "Download"
5. Restart Home Assistant

#### Manual

1. Download the latest release from [Releases](https://github.com/mkshb/ha_av_scenes/releases)
2. Copy the `custom_components/av_scenes` folder to `config/custom_components/`
3. Restart Home Assistant

### Setup

1. **Settings** → **Devices & Services** → **+ Add Integration**
2. Search for "AV Scenes" and select it
3. Click **Configure** to set up rooms and activities

#### Add a Room

1. Select an existing Home Assistant area **or** enter a custom room name
2. Confirm — the room appears in the list immediately

#### Create an Activity

1. Select a room → **Add new activity**
2. Enter a name (e.g., "Watch Movie")
3. Add steps — the wizard guides through configuration:

| Step type | Device | Configurable parameters |
|-----------|--------|------------------------|
| **Turn on device** | Any | — |
| **Set input source** | `media_player` | Input source from device list |
| **Set volume** | `media_player` | Volume 0–100 % |
| **Set sound mode** | `media_player` | Sound mode from device list |
| **Set brightness/color** | `light` | Brightness 0–100 %, color temp, transition |
| **Set color temperature** | `light` | Color temperature 153–500 Mired |
| **Set position** | `cover` | Position 0–100 % |
| **Set tilt** | `cover` | Tilt 0–100 % |
| **Call action** | — | HA service (`domain.service`), optional JSON data |
| **Wait/Delay** | — | Wait 1–60 seconds |

Every step (except Delay) can have an additional `delay_after` that is waited **after** the step completes.

4. Optionally **edit**, **delete**, or **reorder** steps afterwards
5. Optionally **copy** or **rename** activities
6. **Finish activity** — configuration is saved immediately

### Usage

#### Scenes

A HA scene is automatically created for each activity:

```yaml
service: scene.turn_on
target:
  entity_id: scene.living_room_watch_movie
```

#### Services

```yaml
# Start an activity
service: av_scenes.start_activity
data:
  room: living_room
  activity: watch_movie

# Stop the current activity (turns off all devices)
service: av_scenes.stop_activity
data:
  room: living_room

# Reload configuration
service: av_scenes.reload
```

> The `room` ID matches the internal room identifier assigned when the room was created (lowercase, spaces as `_`).

#### Switch Entity

Each room gets a switch showing whether an activity is running:

```yaml
# Is an activity active?
{{ is_state('switch.living_room_activity', 'on') }}

# Which activity is running?
{{ state_attr('switch.living_room_activity', 'current_activity') }}

# All available activities
{{ state_attr('switch.living_room_activity', 'available_activities') }}

# Stop activity
service: switch.turn_off
target:
  entity_id: switch.living_room_activity
```

#### Sensor Entity

Each room gets a configuration sensor:

```yaml
# Current status (idle / starting / active / stopping)
{{ states('sensor.living_room_configuration') }}

# All activity names
{{ state_attr('sensor.living_room_configuration', 'activity_names') }}

# Number of activities
{{ state_attr('sensor.living_room_configuration', 'total_activities') }}
```

**Sensor attributes:**

| Attribute | Description |
|-----------|-------------|
| `room_id` | Internal room ID |
| `room_name` | Display name of the room |
| `total_activities` | Number of configured activities |
| `activity_names` | List of all activity names |
| `activities` | Full details including steps and settings |
| `current_activity` | Name of the active activity or `null` |
| `status` | `idle`, `starting`, `active`, or `stopping` |

### Example Scenarios

#### Movie Night

Steps:

1. Turn on receiver (`delay_after: 3s`)
2. Turn on projector (`delay_after: 10s`)
3. Turn on Blu-ray player (`delay_after: 2s`)
4. Set receiver input to BD/DVD (`delay_after: 1s`)
5. Set receiver volume to 65 %
6. Set cover to 0 % (closed)
7. Dim light to 5 % brightness

#### Smart Activity Switching: Apple TV → Sonos

**Running activity "Apple TV"** uses: Projector, Receiver, Apple TV

**New activity "Sonos"** uses: Receiver, Sonos

What AV Scenes does automatically:
- Projector is **turned off** (no longer needed)
- Apple TV is **turned off** (no longer needed)
- Receiver **stays on** — only input and volume are updated
- Sonos is **turned on**

Result: transition in 2–3 seconds instead of 20–30 seconds.

#### Dependent Devices (Outlet Before TV)

When a TV is connected to a smart outlet, the outlet must be on first:

1. Turn on outlet (`delay_after: 5s`) — TV now has power
2. Set cover to 60 % (`delay_after: 1s`)
3. Dim light to 8 % (`delay_after: 1s`)
4. Turn on TV (`delay_after: 3s`) — boots correctly now
5. Set TV input to HDMI 1 (`delay_after: 1s`)
6. Turn on Apple TV

### Lovelace Examples

#### Activity Card

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Living Room
    entities:
      - entity: switch.living_room_activity
        name: Status
      - type: section
        label: Start activity
      - entity: scene.living_room_watch_movie
        name: Watch Movie
      - entity: scene.living_room_listen_music
        name: Listen to Music
      - entity: scene.living_room_gaming
        name: Gaming
```

#### Markdown Card with Activity List

```yaml
type: markdown
content: |
  ## Living Room — {{ states('sensor.living_room_configuration') }}
  **Activities ({{ state_attr('sensor.living_room_configuration', 'total_activities') }}):**
  {% for a in state_attr('sensor.living_room_configuration', 'activity_names') %}
  - {{ a }}
  {% endfor %}
```

### Automation

```yaml
automation:
  - alias: "Movie night at 8 PM"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.someone_home
        state: "on"
    action:
      - service: av_scenes.start_activity
        data:
          room: living_room
          activity: watch_movie
```

### Known Limitations

- Input source selection requires the `source_list` attribute on the device
- Sound mode selection requires the `sound_mode_list` attribute on the device
- Volume control requires the `media_player.volume_set` service
- Covers with tilt require the `cover.set_cover_tilt_position` service

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'My feature'`
4. Push the branch: `git push origin feature/my-feature`
5. Open a Pull Request

### License & Support

- License: [MIT](LICENSE)
- Bugs & feature requests: [GitHub Issues](https://github.com/mkshb/ha_av_scenes/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
