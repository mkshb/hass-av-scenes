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
- 🔄 **Smart Activity Switching** - Nahtloser Wechsel ohne Geräte neu zu starten
- 🎛️ **Mehrere Entity-Typen** - Media Player, Lichter, Steckdosen und Rollläden
- 🔊 **Lautstärkeregelung** - Automatische Lautstärkenanpassung pro Aktivität
- 💡 **Lichtsteuerung** - Helligkeit, Farbtemperatur und Übergänge
- 🪟 **Rollladen-Steuerung** - Position und Neigung basierend auf Aktivität
- ⚡ **Power Sequencing** - Konfigurierbare Verzögerungen für optimale Gerätesteuerung
- 🎛️ **Input Source Management** - Automatischer Input-Wechsel
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
4. Füge Geräte hinzu:
   - Wähle Gerät aus Dropdown (Media Player, Licht, Steckdose, Rollladen)
   - Konfiguriere gerätespezifische Einstellungen:
     - **Media Player**: Eingangsquelle, Lautstärkeregelung
     - **Licht**: Helligkeit, Farbtemperatur, Übergangszeit
     - **Steckdose**: Nur Ein/Aus mit Verzögerung
     - **Rollladen**: Position und Neigungsposition
   - Setze Einschaltverzögerung (in Sekunden)

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

#### Szenario 2: Von TV zu Apple TV wechseln

**Laufende Aktivität "TV":**
- Receiver (Input: SAT)
- TV
- Sat-Receiver

**Neue Aktivität "Apple TV":**
- Receiver (Input: Apple TV, Lautstärke: 60%)
- TV
- Apple TV

**Smart Switching:**
- ✅ Receiver bleibt AN → Nur Input-Wechsel SAT→Apple TV, Lautstärke 50%→60%
- ✅ TV bleibt AN → Keine Änderung
- ✅ Apple TV bleibt AN
- ❌ Sat-Receiver wird AUSGESCHALTET

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
- 🔄 **Smart Activity Switching** - Seamless transitions without restarting devices
- 🎛️ **Multiple Entity Types** - Media Players, Lights, Switches and Covers
- 🔊 **Volume Control** - Automatic volume adjustment per activity
- 💡 **Light Control** - Brightness, color temperature and transitions
- 🪟 **Cover Control** - Position and tilt based on activity
- ⚡ **Power Sequencing** - Configurable delays for optimal device control
- 🎛️ **Input Source Management** - Automatic input switching
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
4. Add devices:
   - Select device from dropdown (Media Player, Light, Switch, Cover)
   - Configure device-specific settings:
     - **Media Player**: Input source, volume control
     - **Light**: Brightness, color temperature, transition time
     - **Switch**: Only on/off with delay
     - **Cover**: Position and tilt position
   - Set power-on delay (in seconds)

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

#### Scenario 2: Switch from TV to Apple TV

**Running Activity "TV":**
- Receiver (Input: SAT)
- TV
- Satellite Receiver

**New Activity "Apple TV":**
- Receiver (Input: Apple TV, Volume: 60%)
- TV
- Apple TV

**Smart Switching:**
- ✅ Receiver stays ON → Only input change SAT→Apple TV, Volume 50%→60%
- ✅ TV stays ON → No change
- ✅ Apple TV stays ON
- ❌ Satellite Receiver turns OFF

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