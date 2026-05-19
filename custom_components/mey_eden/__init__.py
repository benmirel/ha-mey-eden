"""The Mei Eden Israel integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import MeiEdenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mei Eden from a config entry."""
    coordinator = MeiEdenCoordinator(hass, entry)

    # רענון ראשון - אם נכשל, HA יטפל ברענון אוטומטית
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # האזנה לשינויים בהגדרות (למשל refresh של עוגיות)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options/data update."""
    # רק רענון - בלי טעינה מחדש מלאה (חוסך זמן)
    coordinator: MeiEdenCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.client.set_cookies(entry.data.get("cookies", {}))
