# AV Scenes - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/mkshb/ha_av_scenes.svg)](https://github.com/mkshb/ha_av_scenes/releases)
[![License](https://img.shields.io/github/license/mkshb/ha_av_scenes.svg)](LICENSE)

Home Assistant Integration für aktivitätsbasierte Steuerung von AV-Geräten. Eine Open-Source-Alternative zu Logitech Harmony und Roomie Remote.

[English](#english) | [Deutsch](#deutsch)

---

## Deutsch

### 🎯 Features

**Kernfunktionen:**
- 🏠 **Multiroom-Unterstützung** - Unabhängige Steuerung mehrerer Räume
- 🎬 **Aktivitätsbasierte Szenen** - "Film schauen", "Musik hören", "Gaming", etc.
- 🚀 **Schritt-für-Schritt-Konfiguration** - Granulare Kontrolle mit 11 verschiedenen Schritt-Typen
- 🎯 **Intelligentes Aktivitätswechsel-Management** - Automatisches Ausschalten ungenutzter Geräte
- 🎛️ **Mehrere Entity-Typen** - Media Player, Lichter, Steckdosen und Rollläden
- 🔢 **Schritt-Reihenfolge** - Präzise Kontrolle über die Ausführungssequenz
- 💾 **Persistente Konfiguration** - Alle Einstellungen bleiben nach HA-Neustart erhalten
- 🔊 **Lautstärke & Sound Mode** - Lautstärke und Tonmodus pro Aktivität konfigurierbar
- 💡 **Lichtsteuerung** - Helligkeit, Farbtemperatur und Übergänge
- 🪟 **Rollladen-Steuerung** - Position und Neigung basierend auf Aktivität
- ⚡ **Flexible Delays** - Individuelle Wartezeit nach jedem Schritt (0-60 Sekunden)
- 🎛️ **Input Source Management** - Automatischer Input-Wechsel
- ⚙️ **Call Action** - Beliebige Home Assistant Services in Aktivitäten einbinden
- ✏️ **Edit Step** - Nachträgliche Bearbeitung aller Schritt-Parameter
- 📋 **Aktivität kopieren** - Schnelles Duplizieren bestehender Aktivitäten
- 🗑️ **Raum löschen** - Vollständige Entfernung von Räumen mit allen Aktivitäten
- 📊 **Sensor Entities** - Vollständige Transparenz über Konfiguration in Lovelace
- 🖥️ **UI-basierte Konfiguration** - Kein YAML erforderlich
- 🇩🇪 **Vollständig auf Deutsch** - Komplette deutsche Übersetzung

### 🚀 Installation

#### HACS (Empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu "Integrationen"
3. Klicke auf die drei Punkte oben rechts
4. Wähle "Benutzerdefinierte Repositories"
5. Füge hinzu:
   - **Repository:** `https://github.com/mkshb/ha_av_scenes`
   - **Kategorie:** Integration
6. Klicke auf "AV Scenes" in der Liste
7. Klicke auf "Herunterladen"
8. Starte Home Assistant neu

#### Manuell

1. Lade die neueste Version von [Releases](https://github.com/mkshb/ha_av_scenes/releases) herunter
2. Entpacke die Dateien
3. Kopiere den `custom_components/av_scenes` Ordner in dein `config/custom_components/` Verzeichnis
4. Starte Home Assistant neu

### ⚙️ Konfiguration

1. Gehe zu **Einstellungen** → **Geräte & Dienste**
2. Klicke auf **+ Integration hinzufügen**
3. Suche nach "AV Scenes"
4. Klicke auf **Konfigurieren** um Räume und Aktivitäten einzurichten

#### Raum hinzufügen

1. Wähle einen bestehenden Home Assistant Bereich oder erstelle einen eigenen Raum
2. Klicke auf **Neuen Raum hinzufügen**

#### Aktivität erstellen

1. Wähle einen Raum
2. Klicke auf **Neue Aktivität hinzufügen**
3. Gib einen Namen ein (z.B. "Film schauen")
4. Füge Schritte hinzu:
   - Wähle Schritt-Typ aus 11 verfügbaren Optionen:
     - **Turn on device** - Gerät einschalten
     - **Set input source** - Eingangsquelle wählen (Media Player)
     - **Set volume** - Lautstärke setzen (Media Player)
     - **Set sound mode** - Tonmodus setzen (Media Player) 🆕
     - **Set brightness/color** - Helligkeit/Farbe setzen (Light)
     - **Set color temperature** - Farbtemperatur setzen (Light)
     - **Set position** - Position setzen (Cover)
     - **Set tilt** - Neigung setzen (Cover)
     - **Call action** - Beliebige Home Assistant Action aufrufen 🆕
     - **Wait/Delay** - Wartezeit einfügen
   - Wähle Gerät (außer bei Wait/Delay und Call Action)
   - Konfiguriere schritt-spezifische Parameter
   - Setze Verzögerung nach dem Schritt (0-60 Sekunden)
5. **Schritte bearbeiten** (optional):
   - Wähle "Edit step" um Parameter anzupassen
   - Alle Einstellungen können nachträglich geändert werden
6. **Schritt-Reihenfolge anpassen** (optional):
   - Wähle "Change step order"
   - Verschiebe Schritte nach oben/unten
   - Schritte werden von oben nach unten ausgeführt
7. **Aktivität kopieren** (optional):
   - Nutze "Copy activity" um eine Aktivität zu duplizieren
   - Alle Schritte und Einstellungen werden kopiert
   - Ideal für ähnliche Aktivitäten (z.B. "Film HD" → "Film 4K")

### 📖 Verwendung

#### Szenen

Für jede Aktivität wird automatisch eine Szene erstellt:
```yaml
# Beispiel: Szene aktivieren
service: scene.turn_on
target:
  entity_id: scene.wohnzimmer_film_schauen
```

#### Services

**Aktivität starten:**
```yaml
service: av_scenes.start_activity
data:
  room: wohnzimmer
  activity: film_schauen
```

**Aktivität stoppen:**
```yaml
service: av_scenes.stop_activity
data:
  room: wohnzimmer
```

**Neu laden:**
```yaml
service: av_scenes.reload
```

#### Switches

Jeder Raum erhält einen Switch für den Aktivitätsstatus:
```yaml
# Status prüfen
{{ states('switch.wohnzimmer_activity') }}

# Aktuelle Aktivität
{{ state_attr('switch.wohnzimmer_activity', 'current_activity') }}

# Aktivität stoppen
service: switch.turn_off
target:
  entity_id: switch.wohnzimmer_activity
```

#### Sensors

Jeder Raum erhält einen Konfigurations-Sensor für vollständige Transparenz:
```yaml
# Aktueller Status
{{ states('sensor.wohnzimmer_configuration') }}

# Alle Aktivitäten
{{ state_attr('sensor.wohnzimmer_configuration', 'activity_names') }}

# Detaillierte Aktivitäts-Info
{{ state_attr('sensor.wohnzimmer_configuration', 'activities') }}

# Lovelace Entity Card
type: entity
entity: sensor.wohnzimmer_configuration

# Lovelace Markdown für formatierte Anzeige
type: markdown
content: |
  ## {{ states('sensor.wohnzimmer_configuration') }}

  **Aktivitäten:** {{ state_attr('sensor.wohnzimmer_configuration', 'total_activities') }}

  {% for activity in state_attr('sensor.wohnzimmer_configuration', 'activity_names') %}
  - {{ activity }}
  {% endfor %}
```

**Sensor Attributes enthalten:**
- `activity_names` - Liste aller Aktivitäten
- `activities` - Vollständige Details mit Geräten, Reihenfolge und allen Einstellungen
- `current_activity` - Name der aktuell laufenden Aktivität
- `status` - "active" oder "idle"
- `total_activities` - Anzahl der konfigurierten Aktivitäten

### 🎬 Beispiel-Szenarien

#### Szenario 1: Filmabend

**Geräte:**
- Receiver (Input: BD/DVD, Lautstärke: 65%)
- Beamer (Input: HDMI1)
- Blu-ray Player

**Was passiert:**
1. Alle Geräte werden eingeschaltet
2. Verzögerungen werden eingehalten
3. Receiver-Lautstärke wird auf 65% gesetzt
4. Receiver wechselt auf BD/DVD Input
5. Beamer wechselt auf HDMI1

#### Szenario 2: Von Apple TV zu Sonos wechseln

**Laufende Aktivität "Apple TV":**
- Beamer einschalten
- AV Receiver einschalten
- AV Receiver Input: Apple TV
- AV Receiver Lautstärke: 60%
- Apple TV einschalten

**Neue Aktivität "Sonos":**
- AV Receiver einschalten
- AV Receiver Input: Sonos
- AV Receiver Lautstärke: 50%
- Sonos einschalten

**Intelligentes Aktivitätswechsel-Management:**
- ❌ Beamer wird AUSGESCHALTET (nicht mehr benötigt)
- ❌ Apple TV wird AUSGESCHALTET (nicht mehr benötigt)
- ✅ AV Receiver bleibt AN → Nur Input-Wechsel Apple TV→Sonos, Lautstärke 60%→50%
- ✅ Sonos wird eingeschaltet

#### Szenario 3: Schritt-Reihenfolge für Abhängigkeiten

**Problem:**
- TV ist an Steckdose angeschlossen
- TV schaltet sich ein bevor Steckdose aktiv ist
- TV startet nicht richtig

**Lösung mit Schritt-Reihenfolge:**
1. Turn on Steckdose (delay_after: 5s)
2. Set position Rollladen 60% (delay_after: 1s)
3. Set brightness Licht 8% (delay_after: 1s)
4. Turn on TV (delay_after: 2s)
5. Set source TV → HDMI_IN_4 (delay_after: 1s)
6. Turn on Apple TV (delay_after: 2s)

**Was passiert:**
1. Steckdose wird eingeschaltet → Wartet 5 Sekunden
2. Rollladen fährt auf 60% → Wartet 1 Sekunde
3. Licht geht auf 8% → Wartet 1 Sekunde
4. TV schaltet sich ein (hat jetzt Strom!) → Wartet 2 Sekunden
5. TV wechselt auf HDMI_IN_4 → Wartet 1 Sekunde
6. Apple TV schaltet sich ein → Wartet 2 Sekunden

### 🔧 Erweiterte Konfiguration

#### Lovelace Card Beispiel

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Wohnzimmer Aktivitäten
    entities:
      - entity: switch.wohnzimmer_activity
        name: Aktueller Status
      - type: section
      - entity: scene.wohnzimmer_film_schauen
        name: 🎬 Film schauen
      - entity: scene.wohnzimmer_musik_hoeren
        name: 🎵 Musik hören
      - entity: scene.wohnzimmer_gaming
        name: 🎮 Gaming
      - entity: scene.wohnzimmer_tv
        name: 📺 TV schauen
```

#### Automatisierung Beispiel

```yaml
automation:
  - alias: "Film um 20 Uhr"
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

### 🐛 Bekannte Einschränkungen

- Source-Wechsel funktioniert nur wenn das Gerät das `source_list` Attribut unterstützt
- Lautstärkeregelung funktioniert nur wenn das Gerät den `volume_set` Service unterstützt
- Rollläden mit Neigungsfunktion benötigen Unterstützung für `set_cover_tilt_position` Service

### 🆕 Unterstützte Entity-Typen

- **Media Player** (media_player.*) - Vollständige Unterstützung mit Input-Auswahl und Lautstärkeregelung
- **Lichter** (light.*) - Helligkeit, Farbtemperatur und Übergangszeit
- **Steckdosen** (switch.*) - Ein/Aus Steuerung mit konfigurierbarer Verzögerung
- **Rollläden** (cover.*) - Position und Neigungssteuerung

### 🤝 Beitragen

Contributions sind willkommen! Bitte:

1. Forke das Repository
2. Erstelle einen Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Committe deine Änderungen (`git commit -m 'Add some AmazingFeature'`)
4. Pushe zum Branch (`git push origin feature/AmazingFeature`)
5. Öffne einen Pull Request

### 📝 Changelog

Siehe [CHANGELOG.md](CHANGELOG.md) für Details zu Änderungen.

### 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

### 💬 Support

- 🐛 [Issues](https://github.com/mkshb/ha_av_scenes/issues)
- 💡 [Feature Requests](https://github.com/mkshb/ha_av_scenes/issues)

---

## English

### 🎯 Features

**Core Functionality:**
- 🏠 **Multi-room Support** - Independent control of multiple rooms
- 🎬 **Activity-based Scenes** - "Watch Movie", "Listen to Music", "Gaming", etc.
- 🚀 **Step-by-Step Configuration** - Granular control with 11 different step types
- 🎯 **Intelligent Activity Switching Management** - Automatic shutdown of unused devices
- 🎛️ **Multiple Entity Types** - Media Players, Lights, Switches and Covers
- 🔢 **Step Order Control** - Precise control over execution sequence
- 💾 **Persistent Configuration** - All settings persist after HA restart
- 🔊 **Volume & Sound Mode** - Volume and sound mode configurable per activity
- 💡 **Light Control** - Brightness, color temperature and transitions
- 🪟 **Cover Control** - Position and tilt based on activity
- ⚡ **Flexible Delays** - Individual wait time after each step (0-60 seconds)
- 🎛️ **Input Source Management** - Automatic input switching
- ⚙️ **Call Action** - Integrate any Home Assistant service in activities
- ✏️ **Edit Step** - Modify all step parameters afterwards
- 📋 **Copy Activity** - Quick duplication of existing activities
- 🗑️ **Delete Room** - Complete removal of rooms with all activities
- 📊 **Sensor Entities** - Complete transparency of configuration in Lovelace
- 🖥️ **UI-based Configuration** - No YAML required
- 🇩🇪 **Fully Translated** - Complete German translation

### 🚀 Installation

#### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add:
   - **Repository:** `https://github.com/mkshb/ha_av_scenes`
   - **Category:** Integration
6. Click on "AV Scenes" in the list
7. Click "Download"
8. Restart Home Assistant

#### Manual

1. Download the latest release from [Releases](https://github.com/mkshb/ha_av_scenes/releases)
2. Unzip the files
3. Copy the `custom_components/av_scenes` folder to your `config/custom_components/` directory
4. Restart Home Assistant

### ⚙️ Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "AV Scenes"
4. Click **Configure** to set up rooms and activities

#### Add a Room

1. Select an existing Home Assistant area or create a custom room
2. Click **Add new room**

#### Create an Activity

1. Select a room
2. Click **Add new activity**
3. Enter a name (e.g., "Watch Movie")
4. Add steps:
   - Choose step type from 11 available options:
     - **Turn on device** - Turn on a device
     - **Set input source** - Select input source (Media Player)
     - **Set volume** - Set volume (Media Player)
     - **Set sound mode** - Set sound mode (Media Player) 🆕
     - **Set brightness/color** - Set brightness/color (Light)
     - **Set color temperature** - Set color temperature (Light)
     - **Set position** - Set position (Cover)
     - **Set tilt** - Set tilt (Cover)
     - **Call action** - Call any Home Assistant action 🆕
     - **Wait/Delay** - Insert wait time
   - Select device (except for Wait/Delay and Call Action)
   - Configure step-specific parameters
   - Set delay after step (0-60 seconds)
5. **Edit steps** (optional):
   - Select "Edit step" to adjust parameters
   - All settings can be modified afterwards
6. **Adjust step order** (optional):
   - Select "Change step order"
   - Move steps up/down
   - Steps execute from top to bottom
7. **Copy activity** (optional):
   - Use "Copy activity" to duplicate an activity
   - All steps and settings are copied
   - Ideal for similar activities (e.g., "Movie HD" → "Movie 4K")

### 📖 Usage

#### Scenes

A scene is automatically created for each activity:
```yaml
# Example: Activate scene
service: scene.turn_on
target:
  entity_id: scene.living_room_watch_movie
```

#### Services

**Start activity:**
```yaml
service: av_scenes.start_activity
data:
  room: living_room
  activity: watch_movie
```

**Stop activity:**
```yaml
service: av_scenes.stop_activity
data:
  room: living_room
```

**Reload:**
```yaml
service: av_scenes.reload
```

#### Switches

Each room gets a switch for activity status:
```yaml
# Check status
{{ states('switch.living_room_activity') }}

# Current activity
{{ state_attr('switch.living_room_activity', 'current_activity') }}

# Stop activity
service: switch.turn_off
target:
  entity_id: switch.living_room_activity
```

#### Sensors

Each room gets a configuration sensor for full transparency:
```yaml
# Current status
{{ states('sensor.living_room_configuration') }}

# All activities
{{ state_attr('sensor.living_room_configuration', 'activity_names') }}

# Detailed activity info
{{ state_attr('sensor.living_room_configuration', 'activities') }}

# Lovelace Entity Card
type: entity
entity: sensor.living_room_configuration

# Lovelace Markdown for formatted display
type: markdown
content: |
  ## {{ states('sensor.living_room_configuration') }}

  **Activities:** {{ state_attr('sensor.living_room_configuration', 'total_activities') }}

  {% for activity in state_attr('sensor.living_room_configuration', 'activity_names') %}
  - {{ activity }}
  {% endfor %}
```

**Sensor Attributes contain:**
- `activity_names` - List of all activities
- `activities` - Complete details with devices, order and all settings
- `current_activity` - Name of currently running activity
- `status` - "active" or "idle"
- `total_activities` - Number of configured activities

### 🎬 Example Scenarios

#### Scenario 1: Movie Night

**Devices:**
- Receiver (Input: BD/DVD, Volume: 65%)
- Projector (Input: HDMI1)
- Blu-ray Player

**What happens:**
1. All devices power on
2. Delays are respected
3. Receiver volume is set to 65%
4. Receiver switches to BD/DVD input
5. Projector switches to HDMI1

#### Scenario 2: Switch from Apple TV to Sonos

**Running Activity "Apple TV":**
- Turn on Projector
- Turn on AV Receiver
- AV Receiver Input: Apple TV
- AV Receiver Volume: 60%
- Turn on Apple TV

**New Activity "Sonos":**
- Turn on AV Receiver
- AV Receiver Input: Sonos
- AV Receiver Volume: 50%
- Turn on Sonos

**Intelligent Activity Switching Management:**
- ❌ Projector turns OFF (no longer needed)
- ❌ Apple TV turns OFF (no longer needed)
- ✅ AV Receiver stays ON → Only input change Apple TV→Sonos, Volume 60%→50%
- ✅ Sonos turns on

#### Scenario 3: Step Order for Dependencies

**Problem:**
- TV is connected to power outlet
- TV powers on before outlet is active
- TV doesn't start properly

**Solution with Step Order:**
1. Turn on Outlet (delay_after: 5s)
2. Set position Cover 60% (delay_after: 1s)
3. Set brightness Light 8% (delay_after: 1s)
4. Turn on TV (delay_after: 2s)
5. Set source TV → HDMI_IN_4 (delay_after: 1s)
6. Turn on Apple TV (delay_after: 2s)

**What happens:**
1. Outlet powers on → Waits 5 seconds
2. Cover moves to 60% → Waits 1 second
3. Light dims to 8% → Waits 1 second
4. TV powers on (now has power!) → Waits 2 seconds
5. TV switches to HDMI_IN_4 → Waits 1 second
6. Apple TV powers on → Waits 2 seconds

### 🔧 Advanced Configuration

#### Lovelace Card Example

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Living Room Activities
    entities:
      - entity: switch.living_room_activity
        name: Current Status
      - type: section
      - entity: scene.living_room_watch_movie
        name: 🎬 Watch Movie
      - entity: scene.living_room_listen_music
        name: 🎵 Listen to Music
      - entity: scene.living_room_gaming
        name: 🎮 Gaming
      - entity: scene.living_room_watch_tv
        name: 📺 Watch TV
```

#### Automation Example

```yaml
automation:
  - alias: "Movie at 8 PM"
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

### 🐛 Known Limitations

- Source switching only works if device supports `source_list` attribute
- Volume control only works if device supports `volume_set` service
- Covers with tilt function require support for `set_cover_tilt_position` service

### 🆕 Supported Entity Types

- **Media Players** (media_player.*) - Full support with input selection and volume control
- **Lights** (light.*) - Brightness, color temperature and transition time
- **Switches** (switch.*) - On/off control with configurable delay
- **Covers** (cover.*) - Position and tilt control

### 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for details on changes.

### 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

### 💬 Support

- 🐛 [Issues](https://github.com/mkshb/ha_av_scenes/issues)
- 💡 [Feature Requests](https://github.com/mkshb/ha_av_scenes/issues)