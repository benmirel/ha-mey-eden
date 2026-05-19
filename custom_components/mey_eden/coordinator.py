"""DataUpdateCoordinator for Mei Eden."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MeiEdenApiError, MeiEdenAuthError, MeiEdenClient
from .const import CONF_COOKIES, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MeiEdenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that pulls customer sections and persists fresh cookies."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id[:8]}",
            update_interval=UPDATE_INTERVAL,
        )
        self.hass = hass
        self.entry = entry
        self.client = MeiEdenClient(async_get_clientsession(hass))
        # שחזור עוגיות מהדיסק
        self.client.set_cookies(entry.data.get(CONF_COOKIES, {}))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch new data and persist any refreshed cookies."""
        try:
            # משיכת כל הסקשנים כולל חשבוניות (statements)
            data = await self.client.fetch_sections(
                ["dashboard", "delivery", "equipment", "customer", "statements"]
            )
        except MeiEdenAuthError as err:
            # ה-session פג רשמית
            raise ConfigEntryAuthFailed(str(err)) from err
        except MeiEdenApiError as err:
            # האק הגנה: מג'נטו זורק 400 במקום 401 כשהעוגייה נמחקת
            if "customerId =" in str(err) or "No such entity" in str(err):
                raise ConfigEntryAuthFailed("פג תוקף החיבור למי עדן, יש להתחבר מחדש.") from err
            raise UpdateFailed(str(err)) from err

        # שמירת עוגיות מעודכנות
        new_cookies = self.client.cookies
        if new_cookies and new_cookies != self.entry.data.get(CONF_COOKIES):
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_COOKIES: new_cookies},
            )

        return data