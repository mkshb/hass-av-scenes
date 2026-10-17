"""Tests for the v1 -> v2 config entry migration."""
from __future__ import annotations

import copy

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.av_scenes.const import DOMAIN
from custom_components.av_scenes.migration import migrate_v1_to_v2
from custom_components.av_scenes.model import validate_config

V1_DATA = {
    "rooms": {
        "wohnzimmer": {
            "name": "Wohnzimmer",
            "activities": {
                "TV": {
                    "steps": [
                        {
                            "step_id": "s1",
                            "step_type": "power_on",
                            "entity_id": "media_player.onkyo_receiver",
                            "delay_after": 5,
                            "parameters": {},
                        },
                        {
                            "step_id": "s2",
                            "step_type": "power_on",
                            "entity_id": "media_player.epson_beamer",
                            "delay_after": 10,
                            "parameters": {},
                        },
                        {
                            "step_id": "s3",
                            "step_type": "set_source",
                            "entity_id": "media_player.onkyo_receiver",
                            "delay_after": 0,
                            "parameters": {"input_source": "SAT"},
                        },
                        {
                            "step_id": "s4",
                            "step_type": "set_volume",
                            "entity_id": "media_player.onkyo_receiver",
                            "delay_after": 2,
                            "parameters": {"volume_level": 0.35},
                        },
                        {
                            "step_id": "s5",
                            "step_type": "set_brightness",
                            "entity_id": "light.wz_ambiente",
                            "delay_after": 0,
                            "parameters": {"brightness": 51, "color_temp": 400},
                        },
                        {
                            "step_id": "s6",
                            "step_type": "call_action",
                            "entity_id": "",
                            "delay_after": 0,
                            "parameters": {
                                "action": "script.turn_on",
                                "service_data": {"entity_id": "script.popcorn"},
                            },
                        },
                        {
                            "step_id": "s7",
                            "step_type": "delay",
                            "entity_id": "",
                            "delay_after": 3,
                            "parameters": {},
                        },
                    ]
                },
                "Musik": {
                    "steps": [
                        {
                            "step_id": "m1",
                            "step_type": "power_on",
                            "entity_id": "media_player.onkyo_receiver",
                            "delay_after": 8,
                            "parameters": {},
                        },
                        {
                            "step_id": "m2",
                            "step_type": "set_position",
                            "entity_id": "cover.wz_rollladen",
                            "delay_after": 0,
                            "parameters": {"position": 30},
                        },
                    ]
                },
            },
        }
    }
}


def test_migrate_devices_and_delays() -> None:
    """Every entity becomes one device; delays merge per device."""
    room = migrate_v1_to_v2(V1_DATA)["rooms"]["wohnzimmer"]

    assert room["name"] == "Wohnzimmer"
    assert room["devices"] == {
        "onkyo_receiver": {
            "entity_id": "media_player.onkyo_receiver",
            # max of the power_on delays in TV (5) and Musik (8)
            "delay_after_on": 8,
            # v1 stopped with max(delay_after) of all steps of the entity
            "delay_after_off": 8,
        },
        "epson_beamer": {
            "entity_id": "media_player.epson_beamer",
            "delay_after_on": 10,
            "delay_after_off": 10,
        },
        "wz_ambiente": {
            "entity_id": "light.wz_ambiente",
            "delay_after_on": 0,
            "delay_after_off": 0,
        },
        "wz_rollladen": {
            "entity_id": "cover.wz_rollladen",
            "delay_after_on": 0,
            "delay_after_off": 0,
        },
    }


def test_migrate_activity_steps() -> None:
    """power_on steps become the device list, other steps are flattened."""
    tv = migrate_v1_to_v2(V1_DATA)["rooms"]["wohnzimmer"]["activities"]["TV"]

    assert tv["name"] == "TV"
    assert tv["devices"] == ["onkyo_receiver", "epson_beamer"]
    assert tv["on_start"] == []
    assert tv["steps"] == [
        {"id": "s3", "type": "set_source", "device": "onkyo_receiver", "source": "SAT"},
        {
            "id": "s4",
            "type": "set_volume",
            "device": "onkyo_receiver",
            "volume_level": 0.35,
            "delay_after": 2,
        },
        {
            "id": "s5",
            "type": "set_brightness",
            "device": "wz_ambiente",
            "brightness_pct": 20,
            "color_temp_kelvin": 2500,
        },
        {
            "id": "s6",
            "type": "call_action",
            "action": "script.turn_on",
            "data": {"entity_id": "script.popcorn"},
        },
        {"id": "s7", "type": "delay", "delay_after": 3},
    ]
    # The light had no power_on step: v1 still switched it off on stop
    assert tv["on_stop"] == [
        {"action": "homeassistant.turn_off", "target": {"entity_id": "light.wz_ambiente"}}
    ]


def test_migrate_cover_closed_on_stop() -> None:
    """v1 closed covers on stop; that is kept as an on_stop action."""
    musik = migrate_v1_to_v2(V1_DATA)["rooms"]["wohnzimmer"]["activities"]["Musik"]
    assert musik["devices"] == ["onkyo_receiver"]
    assert musik["on_stop"] == [
        {"action": "cover.close_cover", "target": {"entity_id": "cover.wz_rollladen"}}
    ]


def test_migrate_does_not_touch_input() -> None:
    """The migration works on a copy."""
    before = copy.deepcopy(V1_DATA)
    migrate_v1_to_v2(V1_DATA)
    assert before == V1_DATA


def test_migrated_data_is_valid() -> None:
    """The result passes the v2 schema."""
    validate_config(migrate_v1_to_v2(V1_DATA))


def test_migrate_legacy_device_states() -> None:
    """The pre-0.3 device_states format is converted in the same pass."""
    data = {
        "rooms": {
            "kino": {
                "name": "Kino",
                "activities": {
                    "Film": {
                        "device_states": {
                            "media_player.avr": {
                                "power_on_delay": 4,
                                "input_source": "BD",
                                "is_volume_controller": True,
                                "volume_level": 0.4,
                            },
                            "switch.leinwand": {"power_on_delay": 0},
                        },
                        "device_order": ["switch.leinwand", "media_player.avr"],
                    }
                },
            }
        }
    }
    room = migrate_v1_to_v2(data)["rooms"]["kino"]
    film = room["activities"]["Film"]

    assert film["devices"] == ["leinwand", "avr"]
    assert room["devices"]["avr"]["delay_after_on"] == 4
    assert [s["type"] for s in film["steps"]] == ["set_source", "set_volume"]
    assert "device_states" not in film
    validate_config(migrate_v1_to_v2(data))


def test_migrate_device_key_collision() -> None:
    """Entities with the same object_id get distinct device keys."""
    data = {
        "rooms": {
            "r": {
                "activities": {
                    "a": {
                        "steps": [
                            {"step_type": "power_on", "entity_id": "switch.beamer"},
                            {"step_type": "power_on", "entity_id": "media_player.beamer"},
                        ]
                    }
                }
            }
        }
    }
    room = migrate_v1_to_v2(data)["rooms"]["r"]
    assert room["activities"]["a"]["devices"] == ["beamer", "beamer_2"]
    assert room["devices"]["beamer_2"]["entity_id"] == "media_player.beamer"


def test_migrate_action_and_delay_steps_with_entity() -> None:
    """v1 ran action and delay steps without their entity and only switched it
    off on stop; v2 does not allow a device on these steps."""
    data = {
        "rooms": {
            "r": {
                "activities": {
                    "a": {
                        "steps": [
                            {
                                "step_type": "call_action",
                                "entity_id": "script.popcorn",
                                "delay_after": 2,
                                "parameters": {"action": "script.turn_on"},
                            },
                            {"step_type": "delay", "entity_id": "light.wz", "delay_after": 3},
                        ]
                    }
                }
            }
        }
    }
    migrated = migrate_v1_to_v2(data)
    room = migrated["rooms"]["r"]
    activity = room["activities"]["a"]

    assert [("device" in s) for s in activity["steps"]] == [False, False]
    assert room["devices"] == {}
    assert activity["on_stop"] == [
        {"action": "homeassistant.turn_off", "target": {"entity_id": "light.wz"}},
        {"delay": {"seconds": 3}},
        {"action": "homeassistant.turn_off", "target": {"entity_id": "script.popcorn"}},
        {"delay": {"seconds": 2}},
    ]
    validate_config(migrated)


def test_migrate_keeps_unknown_keys() -> None:
    """Unknown keys survive so nothing is silently lost."""
    data = {
        "extra": 1,
        "rooms": {
            "r": {
                "custom": "x",
                "activities": {
                    "a": {
                        "icon": "mdi:tv",
                        "steps": [
                            {
                                "step_type": "set_source",
                                "entity_id": "media_player.x",
                                "parameters": {"input_source": "A", "foo": "bar"},
                            }
                        ],
                    }
                },
            }
        },
    }
    out = migrate_v1_to_v2(data)
    assert out["extra"] == 1
    assert out["rooms"]["r"]["custom"] == "x"
    assert out["rooms"]["r"]["activities"]["a"]["icon"] == "mdi:tv"
    assert out["rooms"]["r"]["activities"]["a"]["steps"][0]["foo"] == "bar"


async def test_async_migrate_entry(hass: HomeAssistant) -> None:
    """A version 1 entry is migrated on setup."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, data=V1_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data == migrate_v1_to_v2(V1_DATA)
    assert entry.data["rooms"]["wohnzimmer"]["devices"]["epson_beamer"] == {
        "entity_id": "media_player.epson_beamer",
        "delay_after_on": 10,
        "delay_after_off": 10,
    }


async def test_async_migrate_entry_refuses_downgrade(hass: HomeAssistant) -> None:
    """An entry from a newer release is not loaded."""
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={"rooms": {}})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_current_entry_not_migrated(hass: HomeAssistant) -> None:
    """A current entry passes through unchanged."""
    data = migrate_v1_to_v2(V1_DATA)
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, data=data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.data == data
