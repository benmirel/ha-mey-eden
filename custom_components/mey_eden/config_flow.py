"""Config flow for Mei Eden Israel."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MeiEdenApiError, MeiEdenClient
from .const import CONF_COOKIES, CONF_PHONE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeiEdenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mei Eden."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize ephemeral flow state."""
        self._phone_full: str | None = None
        self._phone_prefix: str | None = None
        self._phone_number: str | None = None
        self._client: MeiEdenClient | None = None
        self._reauth_entry: ConfigEntry | None = None

    # ---------- Step 1: phone number ----------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the user's phone number."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE].strip().replace("-", "").replace(" ", "")

            if not (len(phone) == 10 and phone.startswith("05") and phone.isdigit()):
                errors[CONF_PHONE] = "invalid_phone_format"
            else:
                self._phone_full = phone
                self._phone_prefix = phone[:3]
                self._phone_number = phone[3:]

                # מניעת כפילות (אם זה לא flow של reauth)
                if not self._reauth_entry:
                    await self.async_set_unique_id(phone)
                    self._abort_if_unique_id_configured()

                self._client = MeiEdenClient(async_get_clientsession(self.hass))

                try:
                    sent = await self._client.request_sms(
                        self._phone_prefix, self._phone_number
                    )
                except MeiEdenApiError as err:
                    _LOGGER.error("Cannot reach Mei Eden: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if sent:
                        return await self.async_step_verify()
                    errors["base"] = "sms_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PHONE, default="05"): str}
            ),
            errors=errors,
            description_placeholders={
                "info": "הכנס מספר טלפון נייד ישראלי (10 ספרות, מתחיל ב-05)"
            },
        )

    # ---------- Step 2: OTP verification ----------

    async def async_step_verify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the OTP code received via SMS."""
        errors: dict[str, str] = {}

        if user_input is not None and self._client:
            otp_code = user_input["otp_code"].strip()

            try:
                ok = await self._client.verify_otp(
                    self._phone_prefix, self._phone_number, otp_code
                )
            except MeiEdenApiError as err:
                _LOGGER.error("OTP request failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if ok:
                    cookies = self._client.cookies

                    # אם זה flow של reauth - מעדכן את ה-entry הקיים
                    if self._reauth_entry:
                        self.hass.config_entries.async_update_entry(
                            self._reauth_entry,
                            data={
                                **self._reauth_entry.data,
                                CONF_COOKIES: cookies,
                            },
                        )
                        await self.hass.config_entries.async_reload(
                            self._reauth_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")

                    # התקנה חדשה
                    return self.async_create_entry(
                        title=f"מי עדן ({self._phone_full})",
                        data={
                            CONF_PHONE: self._phone_full,
                            CONF_COOKIES: cookies,
                        },
                    )
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="verify",
            data_schema=vol.Schema({vol.Required("otp_code"): str}),
            errors=errors,
            description_placeholders={
                "phone": self._phone_full or "",
            },
        )

    # ---------- Reauth flow (when session expires) ----------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when session cookies expire."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reauth_entry:
            # ממלא מראש את הטלפון מהentry הקיים
            phone = self._reauth_entry.data.get(CONF_PHONE, "")
            if phone:
                self._phone_full = phone
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth - jumps back to user step with phone prefilled."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"phone": self._phone_full or ""},
            )
        return await self.async_step_user({CONF_PHONE: self._phone_full or "05"})
