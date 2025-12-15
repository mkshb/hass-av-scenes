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
CONF_POWER_ON_DELAY: Final = "power_on_delay"
CONF_POWER_OFF_DELAY: Final = "power_off_delay"
CONF_INPUT_SOURCE: Final = "input_source"
CONF_VOLUME_LEVEL: Final = "volume_level"
CONF_IS_VOLUME_CONTROLLER: Final = "is_volume_controller"

# Light-specific configuration
CONF_BRIGHTNESS: Final = "brightness"
CONF_COLOR_TEMP: Final = "color_temp"
CONF_RGB_COLOR: Final = "rgb_color"
CONF_TRANSITION: Final = "transition"

# Cover-specific configuration
CONF_POSITION: Final = "position"
CONF_TILT_POSITION: Final = "tilt_position"

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
