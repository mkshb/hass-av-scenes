# Changelog

Alle wesentlichen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2025-12-16

### 🇩🇪 Deutsch

#### Hinzugefügt
- 🚀 **Schritt-für-Schritt-Konfiguration** - Vollständige Neuentwicklung des Aktivitätssystems
  - Jede Aktivität besteht aus einzelnen, konfigurierbaren Schritten
  - Granulare Kontrolle: Gerät einschalten, Eingang wählen, Lautstärke setzen - alles separate Schritte
  - Beispiel: "1. AV Receiver einschalten → 2. 5 Sek. warten → 3. Eingang auf HDMI 1 → 4. Beamer einschalten"
- ⏱️ **Flexible Delays** - Individuelle Wartezeit nach jedem Schritt
  - Kein globales `power_on_delay` mehr
  - Jeder Schritt hat eigenes `delay_after` (0-60 Sekunden)
  - Ideal für Geräte, die Zeit zum Aufwärmen brauchen
- 🎯 **9 Schritt-Typen** für maximale Flexibilität
  - `power_on` - Gerät einschalten
  - `power_off` - Gerät ausschalten
  - `set_source` - Eingang wählen (Media Player)
  - `set_volume` - Lautstärke setzen (Media Player)
  - `set_brightness` - Helligkeit/Farbe setzen (Light)
  - `set_color_temp` - Farbtemperatur setzen (Light)
  - `set_position` - Position setzen (Cover)
  - `set_tilt` - Neigung setzen (Cover)
  - `delay` - Nur warten (kein Gerät)
- 🔄 **Move Up/Down für Schritte** - Einfache Neuanordnung der Schritte
  - Ähnlich wie bei Geräten
  - Schritte werden von oben nach unten ausgeführt
- 🔄 **Automatische Migration** - Alte Konfigurationen werden automatisch konvertiert
  - Device-basierte Aktivitäten → Step-basierte Aktivitäten
  - Läuft transparent beim Öffnen der Config
  - Keine Daten gehen verloren
- 📊 **Verbesserte Step-Anzeige** - Übersichtliche Liste aller Schritte mit Details
  - "1. Turn on AV Receiver (then wait 5s)"
  - "2. Set AV Receiver source to 'HDMI 1'"
  - "3. Turn on Beamer (then wait 2s)"

#### Geändert
- 🏗️ **Komplett neue Datenstruktur** - Von `device_states` zu `steps`
  - Alte Struktur: Gerät mit allen Einstellungen
  - Neue Struktur: Liste von einzelnen Schritten
  - Viel flexibler und erweiterbar
- 🎛️ **Coordinator umgebaut** - Schrittweise Ausführung statt gerätebasiert
  - Führt Schritte sequenziell aus
  - Wartet nach jedem Schritt gemäß `delay_after`
  - Besseres Logging für jeden Schritt
- 🗑️ **Smart Activity Switching entfernt** - Zu komplex mit Step-System
  - Alle Schritte werden immer ausgeführt
  - Einfacher und vorhersehbarer
  - Bei Bedarf manuell konfigurierbar

### 🇬🇧 English

#### Added
- 🚀 **Step-by-Step Configuration** - Complete redesign of the activity system
  - Each activity consists of individual, configurable steps
  - Granular control: Turn on device, select input, set volume - all separate steps
  - Example: "1. Turn on AV Receiver → 2. Wait 5 sec → 3. Input to HDMI 1 → 4. Turn on Projector"
- ⏱️ **Flexible Delays** - Individual wait time after each step
  - No more global `power_on_delay`
  - Each step has its own `delay_after` (0-60 seconds)
  - Perfect for devices that need warm-up time
- 🎯 **9 Step Types** for maximum flexibility
  - `power_on` - Turn on device
  - `power_off` - Turn off device
  - `set_source` - Select input (Media Player)
  - `set_volume` - Set volume (Media Player)
  - `set_brightness` - Set brightness/color (Light)
  - `set_color_temp` - Set color temperature (Light)
  - `set_position` - Set position (Cover)
  - `set_tilt` - Set tilt (Cover)
  - `delay` - Just wait (no device)
- 🔄 **Move Up/Down for Steps** - Easy step reordering
  - Similar to devices
  - Steps execute from top to bottom
- 🔄 **Automatic Migration** - Old configurations automatically converted
  - Device-based activities → Step-based activities
  - Runs transparently when opening config
  - No data loss
- 📊 **Improved Step Display** - Clear list of all steps with details
  - "1. Turn on AV Receiver (then wait 5s)"
  - "2. Set AV Receiver source to 'HDMI 1'"
  - "3. Turn on Projector (then wait 2s)"

#### Changed
- 🏗️ **Completely New Data Structure** - From `device_states` to `steps`
  - Old structure: Device with all settings
  - New structure: List of individual steps
  - Much more flexible and extensible
- 🎛️ **Coordinator Rebuilt** - Step-by-step execution instead of device-based
  - Executes steps sequentially
  - Waits after each step according to `delay_after`
  - Better logging for each step
- 🗑️ **Smart Activity Switching Removed** - Too complex with step system
  - All steps are always executed
  - Simpler and more predictable
  - Can be configured manually if needed

---

## [0.2.1] - 2025-12-15

### 🇩🇪 Deutsch

#### Hinzugefügt
- 📊 **Sensor Entities für Transparenz** - Jeder Raum erhält einen Konfigurations-Sensor
  - State: Zeigt aktuelle Aktivität oder "Inaktiv"
  - Attributes: Vollständige Details zu allen Aktivitäten und Geräten
  - Geräte-Reihenfolge mit allen Einstellungen sichtbar
  - Ideal für Lovelace-Dashboard Integration
  - Icons wechseln basierend auf Status (aktiv: `mdi:play-circle`, inaktiv: `mdi:information-outline`)

#### Behoben
- 🐛 **Config Persistenz** - Deep copy statt shallow copy in OptionsFlow
  - Verschachtelte Daten (rooms → activities → devices) werden jetzt korrekt kopiert
  - Geräte-Löschungen werden zuverlässig persistiert
  - Geräte-Reihenfolge bleibt nach Änderungen erhalten
  - Keine "Geister-Geräte" mehr in core.config_entries

#### Entfernt
- 🗑️ **Überflüssiger Hilfstext** - `data_description` aus Menüs entfernt
  - "Wähle eine Aktion" Text unter Dropdown-Menüs nicht mehr sichtbar
  - Sauberere UI ohne redundanten Text

### 🇬🇧 English

#### Added
- 📊 **Sensor Entities for Transparency** - Each room gets a configuration sensor
  - State: Shows current activity or "Idle"
  - Attributes: Complete details of all activities and devices
  - Device order with all settings visible
  - Perfect for Lovelace dashboard integration
  - Icons change based on status (active: `mdi:play-circle`, idle: `mdi:information-outline`)

#### Fixed
- 🐛 **Config Persistence** - Deep copy instead of shallow copy in OptionsFlow
  - Nested data (rooms → activities → devices) now copied correctly
  - Device deletions persist reliably
  - Device order remains after changes
  - No more "ghost devices" in core.config_entries

#### Removed
- 🗑️ **Redundant Helper Text** - Removed `data_description` from menus
  - "Choose an action" text below dropdown menus no longer visible
  - Cleaner UI without redundant text

---

## [0.2.0] - 2025-12-15

### 🇩🇪 Deutsch

#### Hinzugefügt
- ✨ **Multi-Entity-Unterstützung** - Integration von Lichtern, Steckdosen und Rollläden zusätzlich zu Media Playern
  - Lichter: Helligkeit (0-100%), Farbtemperatur (Mired), Übergangszeit
  - Steckdosen: Ein/Aus-Steuerung mit konfigurierbarer Verzögerung
  - Rollläden: Position (0-100%) und Neigungsposition
- 🔢 **Geräte-Reihenfolge** - Kontrolle über die Einschalt-Reihenfolge von Geräten
  - Nummerierte Anzeige (1., 2., 3., ...)
  - "Change device order" Funktion zum Nach-oben/Nach-unten verschieben
  - Geräte werden von oben nach unten ausgeführt
  - Wichtig für Abhängigkeiten (z.B. Steckdose vor TV)
- 💾 **Persistente Geräte-Reihenfolge** - Reihenfolge bleibt nach Home Assistant Neustart erhalten
  - Explizite Speicherung der `device_order` Liste
  - Synchronisation mit `device_states` bei jedem Speichern
  - Rückwärtskompatibilität mit bestehenden Konfigurationen
- 🗑️ **Raum löschen** - Funktion zum Löschen von Räumen mit allen Aktivitäten
- 📋 **Aktivität kopieren** - Duplizierung bestehender Aktivitäten inkl. aller Geräte und Einstellungen
- 📊 **Verbesserte Geräte-Anzeige**
  - Friendly Names statt Entity-IDs
  - Einschaltverzögerung bei jedem Gerät sichtbar
  - Übersichtliche Formatierung mit allen wichtigen Parametern
- ⏱️ **Cover-Verzögerungen** - power_on_delay funktioniert jetzt auch bei Rollläden
- 🎨 **Optimierte Menü-Reihenfolge** - "Beenden/Zurück"-Optionen immer am Ende

#### Behoben
- 🐛 Cover-Steuerung verwendet jetzt korrekte Services (open_cover, set_cover_position, close_cover)
- 🐛 Geräte-Reihenfolge wird vor jedem Speichern synchronisiert
- 🐛 Gelöschte Geräte werden aus device_order entfernt

#### Geändert
- 🔄 Coordinator verwendet jetzt device_order für sequentielle Ausführung
- 🔄 Geräte werden beim Ausschalten in umgekehrter Reihenfolge deaktiviert
- 🔄 Menüs zeigen Optionen dynamisch basierend auf Inhalt

### 🇬🇧 English

#### Added
- ✨ **Multi-Entity Support** - Integration of lights, switches and covers in addition to media players
  - Lights: Brightness (0-100%), color temperature (Mired), transition time
  - Switches: On/off control with configurable delay
  - Covers: Position (0-100%) and tilt position
- 🔢 **Device Order Control** - Control over device power-on sequence
  - Numbered display (1., 2., 3., ...)
  - "Change device order" function to move up/down
  - Devices execute from top to bottom
  - Important for dependencies (e.g., outlet before TV)
- 💾 **Persistent Device Order** - Order persists after Home Assistant restart
  - Explicit storage of `device_order` list
  - Synchronization with `device_states` on every save
  - Backward compatibility with existing configurations
- 🗑️ **Delete Room** - Function to delete rooms with all activities
- 📋 **Copy Activity** - Duplicate existing activities including all devices and settings
- 📊 **Improved Device Display**
  - Friendly names instead of entity IDs
  - Power-on delay visible for each device
  - Clear formatting with all important parameters
- ⏱️ **Cover Delays** - power_on_delay now works for covers too
- 🎨 **Optimized Menu Order** - "Finish/Back" options always at the bottom

#### Fixed
- 🐛 Cover control now uses correct services (open_cover, set_cover_position, close_cover)
- 🐛 Device order is synchronized before every save
- 🐛 Deleted devices are removed from device_order

#### Changed
- 🔄 Coordinator now uses device_order for sequential execution
- 🔄 Devices are turned off in reverse order
- 🔄 Menus show options dynamically based on content

---

## [0.1.1] - 2025-12-14

### 🇩🇪 Deutsch

####
- ✅ Sprachfehler behoben

### 🇬🇧 English

####
- ✅ Fixed language errors

---

## [0.1.0] - 2025-12-14

### 🇩🇪 Deutsch

#### Hinzugefügt
- 🎉 Initiales Release
- ✅ Multiroom-Unterstützung mit unabhängiger Steuerung
- ✅ Aktivitätsbasierte Szenen für AV-Geräte
- ✅ **Smart Activity Switching** - Geräte bleiben eingeschaltet beim Wechsel
- ✅ Automatische Lautstärkeregelung pro Aktivität
- ✅ Power Sequencing mit konfigurierbaren Verzögerungen
- ✅ Input Source Management mit Dropdown-Auswahl
- ✅ UI-basierte Konfiguration (kein YAML erforderlich)
- ✅ Vollständige deutsche Übersetzung
- ✅ Englische Übersetzung
- ✅ Home Assistant Area Integration
- ✅ Media Player Picklists
- ✅ Source Picklists (automatisch vom Gerät geladen)
- ✅ Automatische Szenen-Generierung
- ✅ Activity-Status-Switches pro Raum
- ✅ CRUD-Funktionalität für Räume, Aktivitäten und Geräte
- ✅ Auto-Save bei Konfigurationsänderungen
- ✅ Auto-Reload nach Config-Änderungen

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

### 🇬🇧 English

#### Added
- 🎉 Initial release
- ✅ Multi-room support with independent control
- ✅ Activity-based scenes for AV equipment
- ✅ **Smart Activity Switching** - Devices stay on during transitions
- ✅ Automatic volume control per activity
- ✅ Power sequencing with configurable delays
- ✅ Input source management with dropdown selection
- ✅ UI-based configuration (no YAML required)
- ✅ Full German translation
- ✅ English translation
- ✅ Home Assistant area integration
- ✅ Media player picklists
- ✅ Source picklists (automatically loaded from device)
- ✅ Automatic scene generation
- ✅ Activity status switches per room
- ✅ CRUD functionality for rooms, activities and devices
- ✅ Auto-save on configuration changes
- ✅ Auto-reload after config changes

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

### 🇩🇪 Deutsch

#### [0.3.0] - Geplant
- Erweiterte Bedingungen für Aktivitäten (Zeit, Helligkeit, etc.)
- Makro-Unterstützung für komplexe Sequenzen
- Templates für Aktivitäten
- Zeitgesteuerte Übergänge

---

### 🇬🇧 English

#### [0.3.0] - Planned
- Advanced conditions for activities (time, brightness, etc.)
- Macro support for complex sequences
- Activity templates
- Time-based transitions

---

[0.2.0]: https://github.com/mkshb/ha_av_scenes/releases/tag/v0.2.0
[0.1.1]: https://github.com/mkshb/ha_av_scenes/releases/tag/v0.1.1
[0.1.0]: https://github.com/mkshb/ha_av_scenes/releases/tag/v0.1.0