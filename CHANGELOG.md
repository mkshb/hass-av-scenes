# Changelog

Alle wesentlichen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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