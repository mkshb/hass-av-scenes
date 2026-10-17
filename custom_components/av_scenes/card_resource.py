"""The remote control card as a dashboard resource.

Dashboards load their resource list fresh on every page load, and the URL
carries the version, so a browser never runs an old card after an update.
A card added with ``add_extra_js_url`` sits in the page itself instead, which
the frontend's service worker serves from its cache first: after an update
or a restart, a page load could show an old card or none at all.

This works only while resources are kept in storage (the default). With
resources in YAML, the caller falls back to ``add_extra_js_url``.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _storage_resources(hass: HomeAssistant) -> Any | None:
    """The resource collection, if resources are kept in storage."""
    try:
        from homeassistant.components.lovelace.resources import (
            ResourceStorageCollection,
        )
    except ImportError:
        return None
    data = hass.data.get("lovelace")
    resources = getattr(data, "resources", None)
    if resources is None and isinstance(data, dict):
        # Home Assistant before LovelaceData
        resources = data.get("resources")
    return resources if isinstance(resources, ResourceStorageCollection) else None


def _ours(item: dict[str, Any], base: str) -> bool:
    url = str(item.get("url", ""))
    return url == base or url.startswith(f"{base}?")


async def async_register_card_resource(hass: HomeAssistant, base: str, url: str) -> bool:
    """Add the card as a resource or update its version.

    ``base`` is the URL without query, ``url`` the one with the version.
    Returns False when resources are not in storage or could not be changed,
    so the caller can load the card another way.
    """
    resources = _storage_resources(hass)
    if resources is None:
        return False
    try:
        # Loads the collection from storage
        await resources.async_get_info()
        ours = [item for item in resources.async_items() if _ours(item, base)]
        if not ours:
            _LOGGER.debug("Adding dashboard resource %s", url)
            await resources.async_create_item({"res_type": "module", "url": url})
        elif ours[0]["url"] != url:
            _LOGGER.debug("Updating dashboard resource to %s", url)
            await resources.async_update_item(
                ours[0]["id"], {"res_type": "module", "url": url}
            )
        for item in ours[1:]:
            await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001 - the card must not stop the integration
        _LOGGER.warning("Could not register the dashboard resource", exc_info=True)
        return False
    return True


async def async_remove_card_resource(hass: HomeAssistant, base: str) -> None:
    """Remove the card's resource, e.g. when the integration is removed."""
    resources = _storage_resources(hass)
    if resources is None:
        return
    try:
        await resources.async_get_info()
        for item in [i for i in resources.async_items() if _ours(i, base)]:
            await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001 - removing the entry must not fail
        _LOGGER.warning("Could not remove the dashboard resource", exc_info=True)
