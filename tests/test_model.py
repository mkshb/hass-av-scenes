"""Tests for the v2 configuration schema."""
from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.av_scenes.model import (
    async_validate_config,
    find_missing_entities,
    validate_config,
)


def _config(**activity) -> dict:
    return {
        "rooms": {
            "wz": {
                "devices": {
                    "onkyo": {
                        "entity_id": "media_player.onkyo_receiver",
                        "power_switch": "switch.wz_steckdose_multimedia_5_4_grau",
                        "ready": {"timeout": 60, "reload_integration": True},
                    },
                    "beamer": {
                        "entity_id": "media_player.epson_ehtw7400",
                        "delay_after_off": 180,
                    },
                },
                "activities": {"tv": {"devices": ["onkyo", "beamer"], **activity}},
            }
        }
    }


def test_defaults() -> None:
    """Optional keys get defaults."""
    room = validate_config(_config())["rooms"]["wz"]
    assert room["devices"]["onkyo"]["ready"] == {
        "timeout": 60,
        "reload_integration": True,
        "on_timeout": "abort",
    }
    assert room["devices"]["beamer"]["delay_after_on"] == 0
    assert room["activities"]["tv"]["steps"] == []


def test_unknown_device_in_activity() -> None:
    """Activities may only list known devices."""
    data = _config()
    data["rooms"]["wz"]["activities"]["tv"]["devices"].append("vu")
    with pytest.raises(vol.Invalid) as err:
        validate_config(data)
    assert err.value.path == ["rooms", "wz", "activities", "tv", "devices", 2]


def test_unknown_device_in_step() -> None:
    """Steps may only refer to known devices."""
    with pytest.raises(vol.Invalid, match="unknown device 'vu'"):
        validate_config(_config(steps=[{"type": "set_source", "device": "vu", "source": "A"}]))


def test_unknown_step_type() -> None:
    """Unknown step types are rejected with the list of valid ones."""
    with pytest.raises(vol.Invalid, match="unknown step type 'dance'"):
        validate_config(_config(steps=[{"type": "dance"}]))


def test_wait_available_needs_target() -> None:
    """wait_available needs either a device or an entity_id."""
    with pytest.raises(vol.Invalid):
        validate_config(_config(steps=[{"type": "wait_available"}]))
    steps = validate_config(
        _config(steps=[{"type": "wait_available", "entity_id": "media_player.vu_as2b_de"}])
    )["rooms"]["wz"]["activities"]["tv"]["steps"]
    assert steps[0]["on_timeout"] == "abort"
    assert steps[0]["reload_integration"] is False


async def test_hooks_are_validated(hass: HomeAssistant) -> None:
    """on_start / on_stop are checked as HA actions."""
    good = _config(on_start=[{"action": "cover.close_cover", "target": {"area_id": "wz"}}])
    await async_validate_config(hass, good)

    bad = _config(on_stop=[{"delay": "not a time"}])
    with pytest.raises(vol.Invalid) as err:
        await async_validate_config(hass, bad)
    assert err.value.path[:5] == ["rooms", "wz", "activities", "tv", "on_stop"]


async def test_find_missing_entities(hass: HomeAssistant) -> None:
    """Registered entities count as present even without a state."""
    registry = er.async_get(hass)
    # Onkyo without power: in the registry, but no state
    registry.async_get_or_create(
        "media_player", "onkyo", "abc", suggested_object_id="onkyo_receiver"
    )
    hass.states.async_set("switch.wz_steckdose_multimedia_5_4_grau", "off")

    missing = find_missing_entities(hass, _config())
    assert [(m.path, m.entity_id) for m in missing] == [
        ("devices.beamer.entity_id", "media_player.epson_ehtw7400")
    ]


def test_activity_order() -> None:
    """HA stores keys sorted; activities follow `order`, then their name."""
    activities = {
        "kino": {"name": "Kino"},
        "musik": {"name": "Musik", "order": 2},
        "tv": {"name": "TV", "order": 1},
        "alt": {"name": "Zuletzt"},
    }
    validated = validate_config({"rooms": {"wz": {"activities": activities}}})
    assert list(validated["rooms"]["wz"]["activities"]) == ["tv", "musik", "kino", "alt"]


def test_ready_entity_and_state() -> None:
    """ready may check another entity for given states."""
    room = {"devices": {"atv": {"entity_id": "media_player.atv",
                                "ready": {"entity_id": "remote.atv", "state": "on"}}}}
    ready = validate_config({"rooms": {"wz": room}})["rooms"]["wz"]["devices"]["atv"]["ready"]
    assert ready["entity_id"] == "remote.atv"
    assert ready["state"] == ["on"]


def test_quick_select_buttons() -> None:
    """A button has a command or a source; a source needs a media player."""
    def buttons(*items) -> dict:
        return _config(remote={"buttons": list(items)})

    room = validate_config(
        buttons("guide", {"device": "beamer", "source": "HDMI1", "name": "PC"})
    )["rooms"]["wz"]
    assert room["activities"]["tv"]["remote"]["buttons"] == [
        {"command": "guide"},
        {"device": "beamer", "source": "HDMI1", "name": "PC"},
    ]

    for button in (
        {"source": "Netflix"},
        {"device": "beamer", "source": "Netflix", "command": "netflix"},
        {"name": "Nothing"},
    ):
        with pytest.raises(vol.Invalid):
            validate_config(buttons(button))

    data = buttons({"device": "plug", "source": "Netflix"})
    data["rooms"]["wz"]["devices"]["plug"] = {"entity_id": "switch.plug"}
    with pytest.raises(vol.Invalid) as err:
        validate_config(data)
    assert err.value.path == [
        "rooms", "wz", "activities", "tv", "remote", "buttons", 0, "device"
    ]


def test_device_settings() -> None:
    """Device settings name a media player and a setting; favourites are optional."""
    room = validate_config(
        _config(remote={"settings": [
            {"device": "onkyo", "setting": "sound_mode", "options": ["THX", "STEREO"]},
            {"device": "beamer", "setting": "source"},
        ]})
    )["rooms"]["wz"]
    assert room["activities"]["tv"]["remote"]["settings"] == [
        {"device": "onkyo", "setting": "sound_mode", "options": ["THX", "STEREO"]},
        {"device": "beamer", "setting": "source", "options": []},
    ]
    # Without settings the card offers all; an empty list none
    assert "settings" not in validate_config(_config())["rooms"]["wz"]["activities"]["tv"]["remote"]

    # An entity of the device instead of a setting, on any device
    data = _config(remote={"settings": [
        {"device": "onkyo", "entity": "number.onkyo_bass", "name": "Bass"},
        {"device": "plug", "entity": "switch.plug_led"},
    ]})
    data["rooms"]["wz"]["devices"]["plug"] = {"entity_id": "switch.plug"}
    assert validate_config(data)["rooms"]["wz"]["activities"]["tv"]["remote"]["settings"] == [
        {"device": "onkyo", "entity": "number.onkyo_bass", "name": "Bass", "options": []},
        {"device": "plug", "entity": "switch.plug_led", "options": []},
    ]

    for setting, path in (
        ({"device": "onkyo", "entity": "light.lamp"}, ["entity"]),
        ({"device": "onkyo"}, []),
        ({"device": "onkyo", "setting": "source", "entity": "number.x"}, []),
        ({"device": "onkyo", "setting": "volume"}, ["setting"]),
        ({"device": "nope", "setting": "source"}, ["device"]),
        ({"device": "plug", "setting": "source"}, ["device"]),
    ):
        data = _config(remote={"settings": [setting]})
        data["rooms"]["wz"]["devices"]["plug"] = {"entity_id": "switch.plug"}
        with pytest.raises(vol.Invalid) as err:
            validate_config(data)
        if path:
            assert err.value.path[-1] == path[-1]


def test_device_settings_on_a_device() -> None:
    """A device lists its own settings without naming itself; source and
    sound mode need a media player."""
    data = _config()
    data["rooms"]["wz"]["devices"]["onkyo"]["settings"] = [
        {"setting": "sound_mode", "options": ["THX"]},
        {"entity": "number.onkyo_bass", "name": "Bass"},
    ]
    data["rooms"]["wz"]["devices"]["plug"] = {"entity_id": "switch.plug", "settings": []}
    room = validate_config(data)["rooms"]["wz"]
    assert room["devices"]["onkyo"]["settings"] == [
        {"setting": "sound_mode", "options": ["THX"]},
        {"entity": "number.onkyo_bass", "name": "Bass", "options": []},
    ]
    assert room["devices"]["plug"]["settings"] == []
    assert "settings" not in room["devices"]["beamer"]

    for settings in (
        [{"device": "onkyo", "setting": "source"}],  # the device is implied
        [{"name": "Nothing"}],
    ):
        data = _config()
        data["rooms"]["wz"]["devices"]["onkyo"]["settings"] = settings
        with pytest.raises(vol.Invalid):
            validate_config(data)

    data = _config()
    data["rooms"]["wz"]["devices"]["plug"] = {
        "entity_id": "switch.plug", "settings": [{"setting": "source"}],
    }
    with pytest.raises(vol.Invalid) as err:
        validate_config(data)
    assert err.value.path == ["rooms", "wz", "devices", "plug", "settings", 0]


def test_default_activity_must_exist() -> None:
    """The default activity refers to an activity of the room."""
    data = _config()
    data["rooms"]["wz"]["default_activity"] = "tv"
    assert validate_config(data)["rooms"]["wz"]["default_activity"] == "tv"
    data["rooms"]["wz"]["default_activity"] = "kino"
    with pytest.raises(vol.Invalid) as err:
        validate_config(data)
    assert err.value.path == ["rooms", "wz", "default_activity"]
