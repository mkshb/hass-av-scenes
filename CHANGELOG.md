# Changelog

Alle wesentlichen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.7.0] - 2026-10-15

### Added
- **Device profiles per room** – entity, power outlet (`power_switch`), readiness check (`ready`), `delay_after_on` and `delay_after_off` are set once per device instead of in every step
- **Power outlets** – all outlets an activity needs are switched on at once; shared outlets stay on while any device on them is needed, also by a running activity of another room, and are switched off last when stopping
- **Readiness check and `wait_available` step** – event-based wait until an entity is available; optionally reloads its integration to skip the `setup_retry` back-off, again every 5 s while the device does not answer yet; `continue` or `abort` on timeout
- **Readiness of another entity or state** – `ready` and `wait_available` take `entity_id` and `state`, e.g. wait for an Apple TV's remote to be `on` (connected); remote buttons run the check too and reconnect a device that lost its connection before sending
- **Boot time `delay_after_power`** – per device, waited after its power outlet came on and before the device is switched on; for devices that report `off` without power, where the readiness check cannot help
- **Switch-off delay `delay_after_off`** – cool-down per device, e.g. 180 s for a projector before its power is cut
- **`on_start` / `on_stop`** – any Home Assistant actions with conditions, run by Home Assistant's script engine
- **`toggle_activity` action** – stops if something runs, otherwise starts the room's default activity or the last used one; meant for push buttons (e.g. KNX)
- **`default_activity`** per room – the activity a plain "on" starts (room switch, `toggle_activity`), so a single wall button always does the same; set in the panel
- **Cancelling** – a stop during a running start takes effect immediately
- **`error` state** – an aborted start is never reported as `active`; reason in the sensor attribute `error` and in Settings → Repairs; failed steps in `warnings`
- **State survives restarts** – the running activity is restored after a Home Assistant restart
- **Repairs** – entities that do not exist (typo, renamed entity) are reported under Settings → Repairs
- **Configuration panel** – admin page in the sidebar to edit rooms, devices, activities, steps and remote buttons with Home Assistant's own pickers and action editor, plus a YAML view per room; devices and activities are listed and edited on their own page in sections with help texts, rarely needed settings under "Advanced"; a collapsed guide explains the setup, the terms and an example; one button sets up the connection check for devices with a remote entity such as an Apple TV; checks before saving and refuses to overwrite changes made elsewhere
- **Flow of an activity** in the configuration panel – what starting, switching from another activity or stopping does with the configuration being edited: outlets and devices with the action that switches them, boot times, readiness checks with timeout and on-timeout behaviour, steps, actions on start and stop, outlets cut in the background, and the earliest and latest time of each row; computed by the integration (`av_scenes/config/flow`) the same way the engine runs
- **Touch surface** – for navigation that goes to a remote entity (e.g. an Apple TV), the card shows a swipe area instead of the arrow keys: swipes send arrow keys, a tap sends OK; `remote.touchpad` (or "Touch surface" in the panel) turns it on or off per activity, and a key in the card switches between arrow keys and touch surface, remembered per browser
- **Cool-down in the card** – after a stop or a switch to another activity, the card shows which devices cool down and counts down until their outlet is switched off, also while the room is off; a new start that needs the outlet ends it
- **What a start or stop is busy with** – below the progress bar the card names the device and what happens to it (booting, reconnecting, waiting until it is available, switching on or off, the step), with the time left for boot times and waits and the latest end of a readiness check
- **Now playing in the card** – app, title, series with season and episode or artist, artwork and the playback position of the media player the running activity plays on
- **Remote control preview** in the configuration panel – the card as it looks while an activity runs, for the configuration being edited; a tap shows which device gets the button and what runs there instead of sending it; buttons that would do nothing and the device of every button group are listed
- **Remote control card** `custom:av-scenes-remote-card` – power, activities, volume rocker and slider, d-pad, channels, playback and own buttons per room; shows only what the running activity offers; visual editor; registered by the integration as a dashboard resource with its version in the URL, so no cached old card is loaded after an update (with resources in YAML it is loaded on every page instead); suggested in the card picker (Home Assistant 2026.6+) for the entities of a room, with the room already set
- **`send_command` action** – sends a remote button to the device the running activity uses for it (volume, channels, transport, navigation); media players work without configuration
- **`commands`, `remote`, `icon`** – own buttons as Home Assistant actions per device or activity, routing of button groups and extra buttons per activity
- **Quick select** – remote buttons with `device` and `source` select that source on a media player, e.g. an app on an Apple TV; the panel offers the device's source list, which the integration remembers while the device is off or disconnected
- **Device settings in the card** – a collapsible "Settings" section changes the source and sound mode of the running activity's media players and any number, select or switch entity of its devices (slider, list, on/off key), e.g. a receiver's tone controls; automatic, or chosen per activity under `remote: settings` with favourites; closed by default, each browser remembers whether it is open; `send_command` knows `select_sound_mode` and takes a setting's entity ID as command
- **`remote_entity`** per device – the card's arrow keys, OK, back, home and menu go to a remote entity (e.g. an Apple TV's remote) with the key names of its integration; set up together with the connection check by one button in the panel
- **`order`** – position of an activity in lists; Home Assistant stores the configuration with sorted keys, so the written order is not kept across restarts
- **Websocket API** `av_scenes/control/rooms` and `av_scenes/control/subscribe` for the card, `av_scenes/config/get`, `config/validate`, `config/save`, `config/sources`, `config/flow` and `config/remote` (admins only) for the panel
- **Release workflow** – builds the card and attaches `av_scenes.zip`; HACS installs that archive
- **Tests** with `pytest-homeassistant-custom-component` and, for the card, Node's test runner (`npm test`); CI with hassfest and HACS validation

### Changed
- **Scene names** – scenes are named like the other entities of a room, device name plus activity ("AV: Wohnzimmer TV" instead of "Wohnzimmer - TV"); entity IDs of existing scenes stay, names set in Home Assistant are kept
- **Stop without waiting for cool-downs** – a stop is done once the devices are off; outlets whose devices need a cool-down (e.g. 180 s for a projector) are switched off in the background afterwards, so the room and a wall button's status LED do not stay in "stopping" for minutes
- **Reload after power-on** – with `reload_integration`, a device's integration is reloaded once its outlet came on and its boot time passed, even if it still reports a stale state such as `off`; a device its integration reports as unreachable is not switched on, and the activity shows a warning instead of silently missing the command
- **Devices that cannot be switched** (e.g. a Sonos speaker) get no turn-on or turn-off call, instead of a warning on every start and stop
- **Stale entities are removed** – entities of deleted activities and devices of deleted rooms no longer stay behind as "unavailable"
- **IDs of new activities and devices** follow their name or entity in the panel until they are saved, instead of staying "neue_aktivitat" or "device"
- **YAML configuration** – the multi-step click flows are replaced by a YAML editor per room (or for the whole configuration) with validation and the exact error location
- **Changes without reload** – content changes are applied without interrupting running activities
- **Service calls wait for the device** (`blocking`, at most 15 s) instead of only fixed delays
- **Devices that are already on** get no turn-on command and no warm-up delay
- **Smart switching** – outlets that are no longer needed are switched off in the background after the cool-down; the new activity does not wait
- **Switch** – `turn_on` now starts the last used activity
- **Select and scenes** show the activity's display name; actions accept ID or name
- **Activity order** – without `order`, activities are listed by name (after a restart they already were, in alphabetical key order)
- **Actions raise errors** – an unknown room, activity or command is reported to the caller (translated) instead of only being logged
- **Translated entities** – sensor, select and switch use Home Assistant entity translations (English, German) for their names and state labels. **Breaking:** the select's state values are now stable keys: `idle` (was `—`), `starting` and `stopping` (were the German labels "Startet …" and "Stoppt …" with an hourglass or stop symbol in front) and `error`; the labels shown in the UI no longer carry symbols. Automations comparing these values need an update. The switch is now named "Active" ("Aktiv"); existing entity IDs are kept
- **Lights** – brightness as `brightness_pct`, color temperature as `color_temp_kelvin`
- **One entry** – AV Scenes is set up once and holds all rooms; a second entry is refused (the panel and the actions work on rooms by their ID, which would be ambiguous across entries)

### Fixed
- Color temperature steps failed because Home Assistant removed `color_temp` (mireds) from `light.turn_on`
- "Detected blocking call to open … inside the event loop" caused by the debug log at startup
- Migration from version 1 failed when an action or delay step had an entity; the entity is now only switched off on stop, as before
- A start could hang for good when reloading a device's integration never finished; the reload now counts against the readiness timeout and the start goes on with a warning
- The room's select could start the wrong activity when two activities had the same name, or when a name was another activity's ID or a fixed option such as "idle"; such options now carry the activity ID, e.g. "Kino (tv)"
- The room's device ignored the area set for the room and created a new area named like the room; it now goes into the configured area, also when the area is changed later, or into an existing area of the same name

### Removed
- Custom debug log at `/config/av_scenes_debug.log` – use "Enable debug logging" on the integration instead
- Unused constants, including `CONF_POWER_OFF_DELAY`

### Migration
- Existing configurations are migrated automatically from version 1 to 2 without data loss. See "Upgrading from 0.6 and earlier" in the README. **Make a backup first** – older versions cannot load a migrated configuration.

---

## [0.3.1] - 2025-12-17

### Deutsch

#### Behoben
- **HACS Compliance** - Repository-Struktur für HACS korrigiert
  - `custom_components` Verzeichnis in Repository-Root verschoben
  - `hacs.json` hinzugefügt für bessere HACS-Integration
  - Stellt sicher, dass die Integration korrekt über HACS installiert werden kann

### English

#### Fixed
- **HACS Compliance** - Fixed repository structure for HACS
  - Moved `custom_components` directory to repository root
  - Added `hacs.json` for better HACS integration
  - Ensures the integration can be properly installed via HACS

---

## [0.3.0] - 2025-12-17

### Deutsch

#### Hinzugefügt
- **Schritt-für-Schritt-Konfiguration** - Vollständige Neuentwicklung des Aktivitätssystems
  - Jede Aktivität besteht aus einzelnen, konfigurierbaren Schritten
  - Granulare Kontrolle: Gerät einschalten, Eingang wählen, Lautstärke setzen - alles separate Schritte
  - Beispiel: "1. AV Receiver einschalten → 2. 5 Sek. warten → 3. Eingang auf HDMI 1 → 4. Beamer einschalten"
- **Flexible Delays** - Individuelle Wartezeit nach jedem Schritt
  - Kein globales `power_on_delay` mehr
  - Jeder Schritt hat eigenes `delay_after` (0-60 Sekunden)
  - Ideal für Geräte, die Zeit zum Aufwärmen brauchen
- **11 Schritt-Typen** für maximale Flexibilität
  - `power_on` - Gerät einschalten
  - `power_off` - Gerät ausschalten
  - `set_source` - Eingang wählen (Media Player)
  - `set_volume` - Lautstärke setzen (Media Player)
  - `set_sound_mode` - Tonmodus setzen (Media Player) 
  - `set_brightness` - Helligkeit/Farbe setzen (Light)
  - `set_color_temp` - Farbtemperatur setzen (Light)
  - `set_position` - Position setzen (Cover)
  - `set_tilt` - Neigung setzen (Cover)
  - `call_action` - Beliebige Home Assistant Action aufrufen 
  - `delay` - Nur warten (kein Gerät)
- **Sound Mode Support** - Tonmodus für AV Receiver konfigurieren
  - Auswahl aus verfügbaren Sound Modes des Geräts
  - Ideal für verschiedene Audio-Szenarien (Movie, Music, Direct, etc.)
- **Call Action Support** - Beliebige Home Assistant Services aufrufen
  - Format: `domain.service` (z.B. `light.turn_on`, `script.activate`)
  - Optionale Service-Daten als JSON
  - Maximale Flexibilität für komplexe Automationen
- **Edit Step Funktionalität** - Bearbeitung bestehender Schritte
  - Alle Parameter können nachträglich angepasst werden
  - Geräte-Auswahl bleibt erhalten
  - Vollständige Übersetzungen (DE/EN)
- **Move Up/Down für Schritte** - Einfache Neuanordnung der Schritte
  - Ähnlich wie bei Geräten
  - Schritte werden von oben nach unten ausgeführt
- **Automatische Migration** - Alte Konfigurationen werden automatisch konvertiert
  - Device-basierte Aktivitäten → Step-basierte Aktivitäten
  - Läuft transparent beim Öffnen der Config
  - Keine Daten gehen verloren
- **Intelligentes Aktivitätswechsel-Management** - Automatisches Ausschalten ungenutzter Geräte
  - Beim Wechsel zwischen Aktivitäten werden nicht mehr benötigte Geräte ausgeschaltet
  - Beispiel: Wechsel von "Apple TV" (Beamer + AV Receiver + Apple TV) zu "Sonos" (AV Receiver + Sonos)
    - Beamer wird ausgeschaltet (nicht mehr benötigt)
    - Apple TV wird ausgeschaltet (nicht mehr benötigt)
    - AV Receiver bleibt an (wird in beiden verwendet)
  - Geräte werden in umgekehrter Reihenfolge ausgeschaltet
- **Verbesserte Step-Anzeige** - Übersichtliche Liste aller Schritte mit Details
  - "1. Turn on AV Receiver (then wait 5s)"
  - "2. Set AV Receiver source to 'HDMI 1'"
  - "3. Set AV Receiver sound mode to 'Movie'"
  - "4. Turn on Beamer (then wait 2s)"

#### Geändert
- **Komplett neue Datenstruktur** - Von `device_states` zu `steps`
  - Alte Struktur: Gerät mit allen Einstellungen
  - Neue Struktur: Liste von einzelnen Schritten
  - Viel flexibler und erweiterbar
- **Coordinator umgebaut** - Schrittweise Ausführung statt gerätebasiert
  - Führt Schritte sequenziell aus
  - Wartet nach jedem Schritt gemäß `delay_after`
  - Besseres Logging für jeden Schritt
  - Intelligente Geräteverwaltung beim Aktivitätswechsel
- **async_stop_activity aktualisiert** - Verwendet jetzt step-basiertes System
  - Schaltet alle Geräte aus der Aktivität aus
  - Respektiert Geräte-Reihenfolge (umgekehrt)

#### Behoben
- **CONF_ENTITY_ID Import** - Fehlender Import in coordinator.py hinzugefügt
- **Edit Step Übersetzungen** - Fehlende Übersetzungen für Edit-Formular ergänzt

### English

#### Added
- **Step-by-Step Configuration** - Complete redesign of the activity system
  - Each activity consists of individual, configurable steps
  - Granular control: Turn on device, select input, set volume - all separate steps
  - Example: "1. Turn on AV Receiver → 2. Wait 5 sec → 3. Input to HDMI 1 → 4. Turn on Projector"
- **Flexible Delays** - Individual wait time after each step
  - No more global `power_on_delay`
  - Each step has its own `delay_after` (0-60 seconds)
  - Perfect for devices that need warm-up time
- **11 Step Types** for maximum flexibility
  - `power_on` - Turn on device
  - `power_off` - Turn off device
  - `set_source` - Select input (Media Player)
  - `set_volume` - Set volume (Media Player)
  - `set_sound_mode` - Set sound mode (Media Player) 
  - `set_brightness` - Set brightness/color (Light)
  - `set_color_temp` - Set color temperature (Light)
  - `set_position` - Set position (Cover)
  - `set_tilt` - Set tilt (Cover)
  - `call_action` - Call any Home Assistant action 
  - `delay` - Just wait (no device)
- **Sound Mode Support** - Configure sound mode for AV receivers
  - Selection from available sound modes of the device
  - Ideal for different audio scenarios (Movie, Music, Direct, etc.)
- **Call Action Support** - Call any Home Assistant service
  - Format: `domain.service` (e.g., `light.turn_on`, `script.activate`)
  - Optional service data as JSON
  - Maximum flexibility for complex automations
- **Edit Step Functionality** - Edit existing steps
  - All parameters can be adjusted afterwards
  - Device selection is preserved
  - Complete translations (DE/EN)
- **Move Up/Down for Steps** - Easy step reordering
  - Similar to devices
  - Steps execute from top to bottom
- **Automatic Migration** - Old configurations automatically converted
  - Device-based activities → Step-based activities
  - Runs transparently when opening config
  - No data loss
- **Intelligent Activity Switching Management** - Automatic shutdown of unused devices
  - When switching between activities, devices no longer needed are turned off
  - Example: Switch from "Apple TV" (Projector + AV Receiver + Apple TV) to "Sonos" (AV Receiver + Sonos)
    - Projector turns off (no longer needed)
    - Apple TV turns off (no longer needed)
    - AV Receiver stays on (used in both)
  - Devices turn off in reverse order
- **Improved Step Display** - Clear list of all steps with details
  - "1. Turn on AV Receiver (then wait 5s)"
  - "2. Set AV Receiver source to 'HDMI 1'"
  - "3. Set AV Receiver sound mode to 'Movie'"
  - "4. Turn on Projector (then wait 2s)"

#### Changed
- **Completely New Data Structure** - From `device_states` to `steps`
  - Old structure: Device with all settings
  - New structure: List of individual steps
  - Much more flexible and extensible
- **Coordinator Rebuilt** - Step-by-step execution instead of device-based
  - Executes steps sequentially
  - Waits after each step according to `delay_after`
  - Better logging for each step
  - Intelligent device management during activity switching
- **async_stop_activity updated** - Now uses step-based system
  - Turns off all devices from the activity
  - Respects device order (reversed)

#### Fixed
- **CONF_ENTITY_ID Import** - Added missing import in coordinator.py
- **Edit Step Translations** - Added missing translations for edit form

---

## [0.2.1] - 2025-12-15

### Deutsch

#### Hinzugefügt
- **Sensor Entities für Transparenz** - Jeder Raum erhält einen Konfigurations-Sensor
  - State: Zeigt aktuelle Aktivität oder "Inaktiv"
  - Attributes: Vollständige Details zu allen Aktivitäten und Geräten
  - Geräte-Reihenfolge mit allen Einstellungen sichtbar
  - Ideal für Lovelace-Dashboard Integration
  - Icons wechseln basierend auf Status (aktiv: `mdi:play-circle`, inaktiv: `mdi:information-outline`)

#### Behoben
- **Config Persistenz** - Deep copy statt shallow copy in OptionsFlow
  - Verschachtelte Daten (rooms → activities → devices) werden jetzt korrekt kopiert
  - Geräte-Löschungen werden zuverlässig persistiert
  - Geräte-Reihenfolge bleibt nach Änderungen erhalten
  - Keine "Geister-Geräte" mehr in core.config_entries

#### Entfernt
- **Überflüssiger Hilfstext** - `data_description` aus Menüs entfernt
  - "Wähle eine Aktion" Text unter Dropdown-Menüs nicht mehr sichtbar
  - Sauberere UI ohne redundanten Text

### English

#### Added
- **Sensor Entities for Transparency** - Each room gets a configuration sensor
  - State: Shows current activity or "Idle"
  - Attributes: Complete details of all activities and devices
  - Device order with all settings visible
  - Perfect for Lovelace dashboard integration
  - Icons change based on status (active: `mdi:play-circle`, idle: `mdi:information-outline`)

#### Fixed
- **Config Persistence** - Deep copy instead of shallow copy in OptionsFlow
  - Nested data (rooms → activities → devices) now copied correctly
  - Device deletions persist reliably
  - Device order remains after changes
  - No more "ghost devices" in core.config_entries

#### Removed
- **Redundant Helper Text** - Removed `data_description` from menus
  - "Choose an action" text below dropdown menus no longer visible
  - Cleaner UI without redundant text

---

## [0.2.0] - 2025-12-15

### Deutsch

#### Hinzugefügt
- **Multi-Entity-Unterstützung** - Integration von Lichtern, Steckdosen und Rollläden zusätzlich zu Media Playern
  - Lichter: Helligkeit (0-100%), Farbtemperatur (Mired), Übergangszeit
  - Steckdosen: Ein/Aus-Steuerung mit konfigurierbarer Verzögerung
  - Rollläden: Position (0-100%) und Neigungsposition
- **Geräte-Reihenfolge** - Kontrolle über die Einschalt-Reihenfolge von Geräten
  - Nummerierte Anzeige (1., 2., 3., ...)
  - "Change device order" Funktion zum Nach-oben/Nach-unten verschieben
  - Geräte werden von oben nach unten ausgeführt
  - Wichtig für Abhängigkeiten (z.B. Steckdose vor TV)
- **Persistente Geräte-Reihenfolge** - Reihenfolge bleibt nach Home Assistant Neustart erhalten
  - Explizite Speicherung der `device_order` Liste
  - Synchronisation mit `device_states` bei jedem Speichern
  - Rückwärtskompatibilität mit bestehenden Konfigurationen
- **Raum löschen** - Funktion zum Löschen von Räumen mit allen Aktivitäten
- **Aktivität kopieren** - Duplizierung bestehender Aktivitäten inkl. aller Geräte und Einstellungen
- **Verbesserte Geräte-Anzeige**
  - Friendly Names statt Entity-IDs
  - Einschaltverzögerung bei jedem Gerät sichtbar
  - Übersichtliche Formatierung mit allen wichtigen Parametern
- **Cover-Verzögerungen** - power_on_delay funktioniert jetzt auch bei Rollläden
- **Optimierte Menü-Reihenfolge** - "Beenden/Zurück"-Optionen immer am Ende

#### Behoben
- Cover-Steuerung verwendet jetzt korrekte Services (open_cover, set_cover_position, close_cover)
- Geräte-Reihenfolge wird vor jedem Speichern synchronisiert
- Gelöschte Geräte werden aus device_order entfernt

#### Geändert
- Coordinator verwendet jetzt device_order für sequentielle Ausführung
- Geräte werden beim Ausschalten in umgekehrter Reihenfolge deaktiviert
- Menüs zeigen Optionen dynamisch basierend auf Inhalt

### English

#### Added
- **Multi-Entity Support** - Integration of lights, switches and covers in addition to media players
  - Lights: Brightness (0-100%), color temperature (Mired), transition time
  - Switches: On/off control with configurable delay
  - Covers: Position (0-100%) and tilt position
- **Device Order Control** - Control over device power-on sequence
  - Numbered display (1., 2., 3., ...)
  - "Change device order" function to move up/down
  - Devices execute from top to bottom
  - Important for dependencies (e.g., outlet before TV)
- **Persistent Device Order** - Order persists after Home Assistant restart
  - Explicit storage of `device_order` list
  - Synchronization with `device_states` on every save
  - Backward compatibility with existing configurations
- **Delete Room** - Function to delete rooms with all activities
- **Copy Activity** - Duplicate existing activities including all devices and settings
- **Improved Device Display**
  - Friendly names instead of entity IDs
  - Power-on delay visible for each device
  - Clear formatting with all important parameters
- **Cover Delays** - power_on_delay now works for covers too
- **Optimized Menu Order** - "Finish/Back" options always at the bottom

#### Fixed
- Cover control now uses correct services (open_cover, set_cover_position, close_cover)
- Device order is synchronized before every save
- Deleted devices are removed from device_order

#### Changed
- Coordinator now uses device_order for sequential execution
- Devices are turned off in reverse order
- Menus show options dynamically based on content

---

## [0.1.1] - 2025-12-14

### Deutsch

####
- Sprachfehler behoben

### English

####
- Fixed language errors

---

## [0.1.0] - 2025-12-14

### Deutsch

#### Hinzugefügt
- Initiales Release
- Multiroom-Unterstützung mit unabhängiger Steuerung
- Aktivitätsbasierte Szenen für AV-Geräte
- **Smart Activity Switching** - Geräte bleiben eingeschaltet beim Wechsel
- Automatische Lautstärkeregelung pro Aktivität
- Power Sequencing mit konfigurierbaren Verzögerungen
- Input Source Management mit Dropdown-Auswahl
- UI-basierte Konfiguration (kein YAML erforderlich)
- Vollständige deutsche Übersetzung
- Englische Übersetzung
- Home Assistant Area Integration
- Media Player Picklists
- Source Picklists (automatisch vom Gerät geladen)
- Automatische Szenen-Generierung
- Activity-Status-Switches pro Raum
- CRUD-Funktionalität für Räume, Aktivitäten und Geräte
- Auto-Save bei Konfigurationsänderungen
- Auto-Reload nach Config-Änderungen

#### Features im Detail

**Smart Activity Switching:**
- Analysiert welche Geräte in beiden Aktivitäten verwendet werden
- Hält gemeinsame Geräte eingeschaltet
- Aktualisiert nur Input-Source und Lautstärke
- Reduziert Wechselzeit von 20-30 Sekunden auf 2-3 Sekunden

**Services:**
- `av_scenes.start_activity` - Aktivität starten
- `av_scenes.stop_activity` - Aktivität stoppen
- `av_scenes.reload` - Konfiguration neu laden

**Dokumentation:**
- README mit Beispielen
- SMART_SWITCHING.md - Technische Dokumentation
- TRANSLATIONS.md - Übersetzungs-Anleitung

---

### English

#### Added
- Initial release
- Multi-room support with independent control
- Activity-based scenes for AV equipment
- **Smart Activity Switching** - Devices stay on during transitions
- Automatic volume control per activity
- Power sequencing with configurable delays
- Input source management with dropdown selection
- UI-based configuration (no YAML required)
- Full German translation
- English translation
- Home Assistant area integration
- Media player picklists
- Source picklists (automatically loaded from device)
- Automatic scene generation
- Activity status switches per room
- CRUD functionality for rooms, activities and devices
- Auto-save on configuration changes
- Auto-reload after config changes

#### Features in Detail

**Smart Activity Switching:**
- Analyzes which devices are used in both activities
- Keeps shared devices powered on
- Only updates input source and volume
- Reduces transition time from 20-30 seconds to 2-3 seconds

**Services:**
- `av_scenes.start_activity` - Start activity
- `av_scenes.stop_activity` - Stop activity
- `av_scenes.reload` - Reload configuration

**Documentation:**
- README with examples
- SMART_SWITCHING.md - Technical documentation
- TRANSLATIONS.md - Translation guide

---

## Roadmap

### Deutsch

#### [0.4.0] - Geplant
- Erweiterte Bedingungen für Aktivitäten (Zeit, Helligkeit, etc.)
- Makro-Unterstützung für komplexe Sequenzen
- Templates für Aktivitäten
- Zeitgesteuerte Übergänge
- Blueprint-Support für Automatisierungen

---

### English

#### [0.4.0] - Planned
- Advanced conditions for activities (time, brightness, etc.)
- Macro support for complex sequences
- Activity templates
- Time-based transitions
- Blueprint support for automations

---

[0.3.0]: https://github.com/mkshb/hass-av-scenes/releases/tag/v0.3.0
[0.2.1]: https://github.com/mkshb/hass-av-scenes/releases/tag/v0.2.1
[0.2.0]: https://github.com/mkshb/hass-av-scenes/releases/tag/v0.2.0
[0.1.1]: https://github.com/mkshb/hass-av-scenes/releases/tag/v0.1.1
[0.1.0]: https://github.com/mkshb/hass-av-scenes/releases/tag/v0.1.0