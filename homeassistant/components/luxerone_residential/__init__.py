"""The luxerOne integration."""

from __future__ import annotations

from luxerone.client import LuxerOneClient
from luxerone.exceptions import LuxerOneAPIException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, PASS, USER

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _build_client(username: str, password: str) -> LuxerOneClient:
    return LuxerOneClient(username=username, password=password)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up luxerOne instance from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    try:
        hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
            _build_client, entry.data[USER], entry.data[PASS]
        )
    except LuxerOneAPIException as err:
        raise ConfigEntryAuthFailed(err) from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
