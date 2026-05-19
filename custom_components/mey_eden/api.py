"""Mei Eden API client - handles all HTTP communication."""
import logging
import re
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    DEFAULT_HEADERS,
    LOGIN_PAGE_URL,
    SECTIONS_URL,
    SMS_GENERATE_URL,
    SMS_LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)


class MeiEdenAuthError(Exception):
    """Raised when authentication fails or session expired."""


class MeiEdenApiError(Exception):
    """Raised for general API errors."""


class MeiEdenClient:
    """Async client for Mei Eden customer portal (Magento backend)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with a shared aiohttp session."""
        self._session = session
        self._cookies: dict[str, str] = {}
        self._form_key: str | None = None

    # ---------- Cookies management ----------

    @property
    def cookies(self) -> dict[str, str]:
        """Return current cookies dict for persistence."""
        return dict(self._cookies)

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """Restore cookies from saved storage."""
        self._cookies = dict(cookies) if cookies else {}
        if "form_key" in self._cookies:
            self._form_key = self._cookies["form_key"]

    def _merge_response_cookies(self, response: aiohttp.ClientResponse) -> None:
        """Extract Set-Cookie from response and merge into our jar."""
        for cookie_name, morsel in response.cookies.items():
            self._cookies[cookie_name] = morsel.value

        try:
            url = aiohttp.helpers.URL(BASE_URL)
            for cookie in self._session.cookie_jar.filter_cookies(url).values():
                self._cookies[cookie.key] = cookie.value
        except Exception:  # noqa: BLE001
            pass

    # ---------- Login flow ----------

    async def request_sms(self, phone_prefix: str, phone_number: str) -> bool:
        """Step 1: Load login page (to get fresh form_key) then trigger SMS."""
        # 1. פונים לעמוד הבית הראשי במקום פנימי כדי לחמוק מחסימות
        try:
            async with self._session.get(
                BASE_URL,
                headers=DEFAULT_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as resp:
                self._merge_response_cookies(resp)
                html = await resp.text()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed loading login page: %s", err)
            raise MeiEdenApiError(f"Cannot reach Mei Eden: {err}") from err

        # 2. הרג'קס הקטלני שלנו שמוצא את הטוקן מכל החורים האפשריים במג'נטו
        match = re.search(r'form_key["\']?\s*:\s*["\']([a-zA-Z0-9]+)["\']', html)
        if not match:
            match = re.search(r'name=["\']form_key["\']\s+(?:type=["\']hidden["\']\s+)?value=["\']([^"\']+)["\']', html)
            
        if match:
            self._form_key = match.group(1)
        elif "form_key" in self._cookies:
            self._form_key = self._cookies["form_key"]
        else:
            _LOGGER.error("Could not extract form_key from login page")
            raise MeiEdenApiError("form_key not found")

        _LOGGER.debug("Extracted form_key: %s", self._form_key)

        # 3. שליחת בקשת SMS
        payload = {
            "form_key": self._form_key,
            "phone_prefix": phone_prefix,
            "phone_number": phone_number,
            "sms_token_otp": "",
        }
        headers = {
            **DEFAULT_HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": BASE_URL,
        }

        try:
            async with self._session.post(
                SMS_GENERATE_URL,
                data=payload,
                headers=headers,
                cookies=self._cookies,  # 🔥 התיקון הקריטי של העוגיות שקלוד שכח
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                self._merge_response_cookies(resp)
                text = await resp.text()
                _LOGGER.debug("SMS generate response %s: %s", resp.status, text[:200])
                
                if resp.status != 200:
                    return False
                lower = text.lower()
                if "error" in lower and "success" not in lower:
                    _LOGGER.warning("SMS request may have failed: %s", text[:200])
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed sending SMS request: %s", err)
            return False

    async def verify_otp(
        self, phone_prefix: str, phone_number: str, otp_code: str
    ) -> bool:
        """Step 2: Submit OTP code, capture full session cookies."""
        if not self._form_key:
            raise MeiEdenAuthError("No form_key - call request_sms first")

        payload = {
            "form_key": self._form_key,
            "phone_prefix": phone_prefix,
            "phone_number": phone_number,
            "sms_token_otp": otp_code,
        }
        headers = {
            **DEFAULT_HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": BASE_URL,
        }

        try:
            async with self._session.post(
                SMS_LOGIN_URL,
                data=payload,
                headers=headers,
                cookies=self._cookies,  # 🔥 התיקון השני של העוגיות באימות
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
            ) as resp:
                self._merge_response_cookies(resp)
                text = await resp.text()
                _LOGGER.debug("OTP verify response %s: %s", resp.status, text[:200])

                if resp.status not in (200, 302):
                    return False

                if "PHPSESSID" not in self._cookies:
                    _LOGGER.warning("OTP verified but no PHPSESSID received")
                    return False

                if '"error"' in text and '"success":true' not in text:
                    return False

                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed verifying OTP: %s", err)
            return False

    # ---------- Data fetching ----------

    async def fetch_sections(
        self, sections: list[str] | None = None
    ) -> dict[str, Any]:
        """Fetch customer sections (dashboard, delivery, equipment, etc)."""
        if sections is None:
            sections = ["dashboard", "delivery", "equipment", "customer"]

        params = {
            "sections": ",".join(sections),
            "force_new_section_timestamp": "true",
            "_": str(int(__import__("time").time() * 1000)),
        }
        headers = {
            **DEFAULT_HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"{BASE_URL}/myeden/customer/index/",
        }

        try:
            async with self._session.get(
                SECTIONS_URL,
                params=params,
                headers=headers,
                cookies=self._cookies,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                self._merge_response_cookies(resp)

                if resp.status == 401 or resp.status == 403:
                    raise MeiEdenAuthError(
                        f"Session expired (HTTP {resp.status})"
                    )

                if resp.status != 200:
                    body = await resp.text()
                    raise MeiEdenApiError(
                        f"Unexpected status {resp.status}: {body[:200]}"
                    )

                content_type = resp.headers.get("Content-Type", "")
                if "json" not in content_type:
                    text = await resp.text()
                    if "<html" in text.lower() or "login" in text.lower():
                        raise MeiEdenAuthError("Got HTML instead of JSON - session expired")
                    raise MeiEdenApiError(f"Non-JSON response: {text[:200]}")

                data = await resp.json(content_type=None)
                return data
        except aiohttp.ClientError as err:
            raise MeiEdenApiError(f"Network error: {err}") from err