"""DataUpdateCoordinator for Mei Eden with persistence."""
from __future__ import annotations

import logging
import json
import os
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
    """Coordinator that pulls customer sections and persists to cache."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id[:8]}",
            update_interval=UPDATE_INTERVAL,
        )
        self.hass = hass
        self.entry = entry
        self.client = MeiEdenClient(async_get_clientsession(hass))
        self.client.set_cookies(entry.data.get(CONF_COOKIES, {}))
        
        # נתיב לקובץ הגיבוי המקומי
        self.cache_path = hass.config.path(f".{DOMAIN}_{entry.entry_id}_cache.json")
        
        # טעינה ראשונית מהזיכרון הלוקאלי (כדי לא להיות unavailable בריסטרט)
        self.data = self._load_cache()

    def _load_cache(self) -> dict[str, Any] | None:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error("Failed to load cache: %s", e)
        return None

    def _save_cache(self, data: dict[str, Any]):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            _LOGGER.error("Failed to save cache: %s", e)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data, save to cache if success, fallback to cache if fail."""
        try:
            # משיכת הנתונים
            data = await self.client.fetch_sections(
                ["dashboard", "delivery", "equipment", "customer"]
            )
            
            # שמירה לקובץ לוקאלי
            self._save_cache(data)

            # עדכון עוגיות
            new_cookies = self.client.cookies
            if new_cookies and new_cookies != self.entry.data.get(CONF_COOKIES):
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, CONF_COOKIES: new_cookies},
                )
            return data

        except (MeiEdenAuthError, MeiEdenApiError) as err:
            # בודקים האם זו שגיאת אימות (התנתקות/עוגיה שפגה)
            is_auth_error = isinstance(err, MeiEdenAuthError) or "customerId =" in str(err) or "No such entity" in str(err)
            
            # == הגיבוי הלוקאלי נכנס לפעולה ==
            if self.data:
                _LOGGER.warning("משיכה נכשלה, משתמש בנתונים אחרונים מהזיכרון. שגיאה: %s", err)
                
                # אם זו התנתקות ויש לנו קאש - נשלח נוטיפיקציה!
                if is_auth_error:
                    # שולח פוש לטלפון (לכל המכשירים המחוברים ל-HA)
                    self.hass.async_create_task(
                        self.hass.services.async_call(
                            "notify", "notify", 
                            {
                                "title": "💧 התראה: מי עדן התנתק!",
                                "message": "החיבור לתוסף פג תוקף, לכן מוצגים נתונים ישנים מהזיכרון. יש להיכנס להגדרות ולהתחבר מחדש."
                            }
                        )
                    )
                    # מוסיף גם התראה כתומה בפעמון בתוך הממשק של Home Assistant
                    self.hass.components.persistent_notification.async_create(
                        "החיבור למי עדן פג תוקף והמערכת מציגה נתונים ישנים. נא להיכנס להגדרות התוספים ולהתחבר מחדש.",
                        title="💧 תקלת התחברות במי עדן",
                        notification_id="mei_eden_auth_failed"
                    )
                
                return self.data
            
            if is_auth_error:
                raise ConfigEntryAuthFailed("פג תוקף החיבור - נא להתחבר מחדש.") from err
            
            raise UpdateFailed(str(err)) from err