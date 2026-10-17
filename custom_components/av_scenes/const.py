"""Constants for the AV Scenes integration."""
from typing import Final

DOMAIN: Final = "av_scenes"

# Common prefix for the device name on all platforms
DEVICE_NAME_PREFIX: Final = "AV"

# Config entry schema version (see migration.py)
CONFIG_VERSION: Final = 2
CONFIG_MINOR_VERSION: Final = 1

# Configuration keys (schema v2: rooms -> devices / activities -> steps)
CONF_ROOMS: Final = "rooms"
CONF_ACTIVITIES: Final = "activities"
CONF_DEVICES: Final = "devices"
CONF_ENTITY_ID: Final = "entity_id"
CONF_STEPS: Final = "steps"
CONF_NAME: Final = "name"
CONF_AREA_ID: Final = "area_id"
CONF_DEFAULT_ACTIVITY: Final = "default_activity"
CONF_DEVICE: Final = "device"
CONF_POWER_SWITCH: Final = "power_switch"
CONF_READY: Final = "ready"
CONF_REMOTE_ENTITY: Final = "remote_entity"
CONF_TIMEOUT: Final = "timeout"
CONF_STATE: Final = "state"
CONF_RELOAD_INTEGRATION: Final = "reload_integration"
CONF_ON_TIMEOUT: Final = "on_timeout"
CONF_DELAY_AFTER_ON: Final = "delay_after_on"
CONF_DELAY_AFTER_OFF: Final = "delay_after_off"
CONF_DELAY_AFTER_POWER: Final = "delay_after_power"
CONF_ON_START: Final = "on_start"
CONF_ON_STOP: Final = "on_stop"
CONF_ID: Final = "id"
CONF_TYPE: Final = "type"
CONF_ICON: Final = "icon"
CONF_ORDER: Final = "order"
CONF_COMMANDS: Final = "commands"
CONF_REMOTE: Final = "remote"
CONF_BUTTONS: Final = "buttons"
CONF_TOUCHPAD: Final = "touchpad"
CONF_COMMAND: Final = "command"

# Step parameters
CONF_SOURCE: Final = "source"
CONF_VOLUME_LEVEL: Final = "volume_level"
CONF_SOUND_MODE: Final = "sound_mode"
CONF_TRANSITION: Final = "transition"
CONF_POSITION: Final = "position"
CONF_TILT_POSITION: Final = "tilt_position"
CONF_ACTION: Final = "action"
CONF_BRIGHTNESS_PCT: Final = "brightness_pct"
CONF_COLOR_TEMP_KELVIN: Final = "color_temp_kelvin"
CONF_DATA: Final = "data"
CONF_TARGET: Final = "target"

ON_TIMEOUT_CONTINUE: Final = "continue"
ON_TIMEOUT_ABORT: Final = "abort"
ON_TIMEOUT_OPTIONS: Final = [ON_TIMEOUT_CONTINUE, ON_TIMEOUT_ABORT]

DEFAULT_READY_TIMEOUT: Final = 60
# Upper bound for a single blocking service call during an activity
DEFAULT_SERVICE_TIMEOUT: Final = 15

# Step types
STEP_TYPE_POWER_ON: Final = "power_on"
STEP_TYPE_POWER_OFF: Final = "power_off"
STEP_TYPE_SET_SOURCE: Final = "set_source"
STEP_TYPE_SET_VOLUME: Final = "set_volume"
STEP_TYPE_SET_SOUND_MODE: Final = "set_sound_mode"
STEP_TYPE_SET_BRIGHTNESS: Final = "set_brightness"
STEP_TYPE_SET_COLOR_TEMP: Final = "set_color_temp"
STEP_TYPE_SET_POSITION: Final = "set_position"
STEP_TYPE_SET_TILT: Final = "set_tilt"
STEP_TYPE_CALL_ACTION: Final = "call_action"
STEP_TYPE_DELAY: Final = "delay"
STEP_TYPE_WAIT_AVAILABLE: Final = "wait_available"

# Activity states
ACTIVITY_STATE_IDLE: Final = "idle"
ACTIVITY_STATE_STARTING: Final = "starting"
ACTIVITY_STATE_ACTIVE: Final = "active"
ACTIVITY_STATE_STOPPING: Final = "stopping"
ACTIVITY_STATE_ERROR: Final = "error"

# Services
SERVICE_START_ACTIVITY: Final = "start_activity"
SERVICE_STOP_ACTIVITY: Final = "stop_activity"
SERVICE_TOGGLE_ACTIVITY: Final = "toggle_activity"
SERVICE_RELOAD: Final = "reload"
SERVICE_SEND_COMMAND: Final = "send_command"

# Attributes
ATTR_ROOM: Final = "room"
ATTR_ACTIVITY: Final = "activity"
ATTR_COMMAND: Final = "command"
ATTR_DEVICE: Final = "device"
ATTR_VALUE: Final = "value"
ATTR_CURRENT_ACTIVITY: Final = "current_activity"
ATTR_AVAILABLE_ACTIVITIES: Final = "available_activities"

# Remote control: command groups an activity routes to one device each
GROUP_VOLUME: Final = "volume"
GROUP_CHANNELS: Final = "channels"
GROUP_TRANSPORT: Final = "transport"
GROUP_NAVIGATION: Final = "navigation"
COMMAND_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    GROUP_VOLUME: ("volume_up", "volume_down", "mute", "volume_set"),
    GROUP_CHANNELS: ("channel_up", "channel_down"),
    GROUP_TRANSPORT: ("play_pause", "play", "pause", "stop", "next", "previous"),
    GROUP_NAVIGATION: (
        "up", "down", "left", "right", "ok", "back", "menu", "home", "info", "guide", "exit",
    ),
}

# Signal sent whenever the state or configuration of a room changes
SIGNAL_ROOMS_UPDATED: Final = f"{DOMAIN}_rooms_updated"

# Frontend
FRONTEND_URL_BASE: Final = f"/{DOMAIN}_static"
CARD_FILENAME: Final = "av-scenes-card.js"
PANEL_FILENAME: Final = "av-scenes-panel.js"
PANEL_URL_PATH: Final = "av-scenes"
