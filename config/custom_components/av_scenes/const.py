"""Constants for the AV Scenes integration."""
from typing import Final

DOMAIN: Final = "av_scenes"

# Configuration keys
CONF_ROOMS: Final = "rooms"
CONF_ACTIVITIES: Final = "activities"
CONF_DEVICES: Final = "devices"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_ENTITY_ID: Final = "entity_id"
CONF_ACTIVITY_NAME: Final = "activity_name"
CONF_DEVICE_STATES: Final = "device_states"
CONF_DEVICE_ORDER: Final = "device_order"
CONF_POWER_ON_DELAY: Final = "power_on_delay"
CONF_POWER_OFF_DELAY: Final = "power_off_delay"
CONF_INPUT_SOURCE: Final = "input_source"
CONF_VOLUME_LEVEL: Final = "volume_level"
CONF_SOUND_MODE: Final = "sound_mode"
CONF_IS_VOLUME_CONTROLLER: Final = "is_volume_controller"

# Step-based configuration
CONF_STEPS: Final = "steps"
CONF_STEP_ID: Final = "step_id"
CONF_STEP_TYPE: Final = "step_type"
CONF_STEP_DELAY_AFTER: Final = "delay_after"
CONF_STEP_PARAMETERS: Final = "parameters"

# Light-specific configuration
CONF_BRIGHTNESS: Final = "brightness"
CONF_COLOR_TEMP: Final = "color_temp"
CONF_RGB_COLOR: Final = "rgb_color"
CONF_TRANSITION: Final = "transition"

# Cover-specific configuration
CONF_POSITION: Final = "position"
CONF_TILT_POSITION: Final = "tilt_position"

# Action call configuration
CONF_ACTION: Final = "action"
CONF_SERVICE_DATA: Final = "service_data"

# Device types
DEVICE_TYPE_RECEIVER: Final = "receiver"
DEVICE_TYPE_PROJECTOR: Final = "projector"
DEVICE_TYPE_TV: Final = "tv"
DEVICE_TYPE_MEDIA_PLAYER: Final = "media_player"
DEVICE_TYPE_LIGHT: Final = "light"
DEVICE_TYPE_SWITCH: Final = "switch"
DEVICE_TYPE_COVER: Final = "cover"

DEVICE_TYPES: Final = [
    DEVICE_TYPE_RECEIVER,
    DEVICE_TYPE_PROJECTOR,
    DEVICE_TYPE_TV,
    DEVICE_TYPE_MEDIA_PLAYER,
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_SWITCH,
    DEVICE_TYPE_COVER,
]

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

STEP_TYPES: Final = [
    STEP_TYPE_POWER_ON,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_VOLUME,
    STEP_TYPE_SET_SOUND_MODE,
    STEP_TYPE_SET_BRIGHTNESS,
    STEP_TYPE_SET_COLOR_TEMP,
    STEP_TYPE_SET_POSITION,
    STEP_TYPE_SET_TILT,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
]

# Activity states
ACTIVITY_STATE_IDLE: Final = "idle"
ACTIVITY_STATE_STARTING: Final = "starting"
ACTIVITY_STATE_ACTIVE: Final = "active"
ACTIVITY_STATE_STOPPING: Final = "stopping"

# Default values
DEFAULT_POWER_ON_DELAY: Final = 2
DEFAULT_POWER_OFF_DELAY: Final = 1

# Services
SERVICE_START_ACTIVITY: Final = "start_activity"
SERVICE_STOP_ACTIVITY: Final = "stop_activity"
SERVICE_RELOAD: Final = "reload"

# Attributes
ATTR_ROOM: Final = "room"
ATTR_ACTIVITY: Final = "activity"
ATTR_CURRENT_ACTIVITY: Final = "current_activity"
ATTR_AVAILABLE_ACTIVITIES: Final = "available_activities"
