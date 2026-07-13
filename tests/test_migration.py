"""Tests for the device_states -> steps migration."""
from custom_components.av_scenes.config_flow import _migrate_device_states_to_steps
from custom_components.av_scenes.const import (
    CONF_STEPS,
    CONF_STEP_TYPE,
    CONF_ENTITY_ID,
    CONF_STEP_PARAMETERS,
    CONF_INPUT_SOURCE,
    CONF_VOLUME_LEVEL,
    STEP_TYPE_POWER_ON,
    STEP_TYPE_SET_SOURCE,
    STEP_TYPE_SET_VOLUME,
)


def test_already_steps_is_noop():
    """Activities already in steps format are returned unchanged."""
    data = {CONF_STEPS: [{"foo": "bar"}]}
    assert _migrate_device_states_to_steps(data) is data


def test_empty_activity_gets_empty_steps():
    """An activity without device_states migrates to an empty steps list."""
    assert _migrate_device_states_to_steps({}) == {CONF_STEPS: []}


def test_media_player_expands_to_power_source_volume():
    """A media_player device with source + volume becomes ordered steps."""
    activity = {
        "device_states": {
            "media_player.receiver": {
                "input_source": "HDMI 1",
                "is_volume_controller": True,
                "volume_level": 0.4,
                "power_on_delay": 3,
            }
        },
        "device_order": ["media_player.receiver"],
    }

    result = _migrate_device_states_to_steps(activity)
    steps = result[CONF_STEPS]

    types = [s[CONF_STEP_TYPE] for s in steps]
    assert types == [STEP_TYPE_POWER_ON, STEP_TYPE_SET_SOURCE, STEP_TYPE_SET_VOLUME]
    assert all(s[CONF_ENTITY_ID] == "media_player.receiver" for s in steps)
    assert steps[1][CONF_STEP_PARAMETERS][CONF_INPUT_SOURCE] == "HDMI 1"
    assert steps[2][CONF_STEP_PARAMETERS][CONF_VOLUME_LEVEL] == 0.4


def test_device_order_is_respected():
    """Steps follow the configured device_order."""
    activity = {
        "device_states": {
            "switch.b": {"power_on_delay": 0},
            "switch.a": {"power_on_delay": 0},
        },
        "device_order": ["switch.a", "switch.b"],
    }

    result = _migrate_device_states_to_steps(activity)
    entities = [s[CONF_ENTITY_ID] for s in result[CONF_STEPS]]
    assert entities == ["switch.a", "switch.b"]
