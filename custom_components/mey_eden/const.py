"""Constants for the Mei Eden integration."""
from datetime import timedelta

DOMAIN = "mei_eden"
PLATFORMS = ["sensor"]

# Base URL - שם הדומיין הנכון של מי עדן (עם y)
BASE_URL = "https://www.meyeden.co.il"

# URLs לקריאות ל-API
LOGIN_PAGE_URL = f"{BASE_URL}/myeden/customer_login/"
SMS_GENERATE_URL = f"{BASE_URL}/myeden/customer_login/smsgenerate/"
SMS_LOGIN_URL = f"{BASE_URL}/myeden/customer_login/login/"
SECTIONS_URL = f"{BASE_URL}/customer/section/load/"

# UPDATED INTERVAL TO 30 MINUTES, TRYING COOKIE DISCONNECT BYPASS
UPDATE_INTERVAL = timedelta(minutes=30)

# Headers שמדמים דפדפן רגיל
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Storage keys
CONF_COOKIES = "cookies"
CONF_FORM_KEY = "form_key"
CONF_PHONE = "phone"
