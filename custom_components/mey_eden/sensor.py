"""Mei Eden sensors."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_PHONE
from .coordinator import MeiEdenCoordinator

_LOGGER = logging.getLogger(__name__)

ILS = "₪"


def _parse_dt(raw: Any) -> datetime | None:
    """Parse Mei Eden date strings like '2026-05-20T00:00:00'."""
    if not raw or not isinstance(raw, str):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mei Eden sensors from a config entry."""
    coordinator: MeiEdenCoordinator = hass.data[DOMAIN][entry.entry_id]
    customer_number = entry.data.get(CONF_PHONE) or entry.entry_id

    async_add_entities([
        # --- משלוחים ---
        MeiEdenNextDeliverySensor(coordinator, customer_number),
        MeiEdenSecondDeliverySensor(coordinator, customer_number),
        MeiEdenDeliveryFrequencySensor(coordinator, customer_number),
        MeiEdenConsumptionSensor(coordinator, customer_number),
        MeiEdenUrgentDeliverySensor(coordinator, customer_number),
        # --- כספים ---
        MeiEdenBalanceSensor(coordinator, customer_number),
        MeiEdenLastInvoiceSensor(coordinator, customer_number),
        MeiEdenOverdueSensor(coordinator, customer_number),
        # --- ציוד ---
        MeiEdenEquipmentNameSensor(coordinator, customer_number),
        MeiEdenEquipmentInstallDateSensor(coordinator, customer_number),
        MeiEdenEquipmentOwnershipSensor(coordinator, customer_number),
        # --- חשבון ---
        MeiEdenStatusSensor(coordinator, customer_number),
        MeiEdenAddressSensor(coordinator, customer_number),
        MeiEdenCustomerNameSensor(coordinator, customer_number),
        MeiEdenIsPackageSensor(coordinator, customer_number),
    ])


class MeiEdenBaseSensor(CoordinatorEntity[MeiEdenCoordinator], SensorEntity):
    """Base class - groups all sensors under one device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeiEdenCoordinator,
        customer_number: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._customer_number = str(customer_number)
        self._attr_unique_id = f"mei_eden_{customer_number}_{key}"
        
        # FORCING ENGLISH NAMES
        self.entity_id = f"sensor.mei_eden_{customer_number}_{key}"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(customer_number))},
            name=f"מי עדן ({customer_number})",
            manufacturer="Mei Eden",
            model="חשבון לקוח",
            configuration_url="https://www.meyeden.co.il/myeden/customer/index/",
        )

    def _get_value(self, key: str, default: Any = None) -> Any:
        """חילוץ ערך חכם שסורק את כל הסקשנים של מג'נטו."""
        data = self.coordinator.data or {}
        if "dashboard" in data and isinstance(data["dashboard"], dict):
            if key in data["dashboard"]:
                return data["dashboard"][key]
        for section in data.values():
            if isinstance(section, dict):
                if key in section:
                    return section[key]
                for sub_section in section.values():
                    if isinstance(sub_section, dict) and key in sub_section:
                        return sub_section[key]
        return default

    def _get_section(self, *keys: str, default: Any = None) -> Any:
        """גישה ישירה לנתיב מסוים בתוך dashboard.sections."""
        data = self.coordinator.data or {}
        obj = data.get("dashboard", {}).get("sections", {})
        for k in keys:
            if not isinstance(obj, (dict, list)):
                return default
            if isinstance(obj, list):
                try:
                    obj = obj[int(k)]
                except (ValueError, IndexError):
                    return default
            else:
                obj = obj.get(k)
                if obj is None:
                    return default
        return obj if obj is not None else default


class MeiEdenNextDeliverySensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:water-truck"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "next_delivery")
        self._attr_name = "משלוח קרוב"

    @property
    def native_value(self):
        raw = self._get_value("NextDeliveryDate")
        dt = _parse_dt(raw)
        return dt.date() if dt else None


class MeiEdenSecondDeliverySensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "second_delivery")
        self._attr_name = "משלוח הבא אחריו"

    @property
    def native_value(self):
        raw = self._get_value("SecondNextDeliveryDate")
        dt = _parse_dt(raw)
        return dt.date() if dt else None


class MeiEdenBalanceSensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:cash"
    _attr_native_unit_of_measurement = ILS

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "balance")
        self._attr_name = "יתרה לתשלום"

    @property
    def native_value(self):
        balance = self._get_value("CustomerBalance")
        try:
            return float(balance) if balance is not None else 0.0
        except (TypeError, ValueError):
            return 0.0


class MeiEdenDeliveryFrequencySensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:repeat-variant"
    _attr_native_unit_of_measurement = "שבועות"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "delivery_frequency")
        self._attr_name = "תדירות משלוח"

    @property
    def native_value(self):
        freq = self._get_value("DeliveryFrequency")
        try:
            return int(freq) if freq is not None else None
        except (TypeError, ValueError):
            return freq


class MeiEdenConsumptionSensor(MeiEdenBaseSensor):
    """
    מחשב נפח מים ממוצע למשלוח בליטרים לפי הנוסחה:
      ממוצע ליטרים ב-3 חודשים אחרונים * (שבועות בין משלוחים / 4.33)
    """
    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "ליטר"

    WEEKS_PER_MONTH = 4.33

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "consumption")
        self._attr_name = "צריכה משוערת / כמות"

    def _calc_liters_per_delivery(self) -> float | None:
        """חישוב נפח הליטרים הצפוי למשלוח הבא."""
        consumption: list = self._get_value("Consumption")
        freq_weeks = self._get_value("DeliveryFrequency")

        if not isinstance(consumption, list) or not consumption:
            return None
        if not freq_weeks:
            return None

        recent = consumption[-3:]
        avg_liters = sum(c.get("Liters", 0) for c in recent if isinstance(c, dict)) / len(recent)

        if avg_liters <= 0:
            return None

        liters_per_delivery = avg_liters * (float(freq_weeks) / self.WEEKS_PER_MONTH)
        return liters_per_delivery

    @property
    def native_value(self) -> int:
        result = self._calc_liters_per_delivery()
        if result is None:
            return 0
        return round(result)

    @property
    def extra_state_attributes(self) -> dict:
        consumption = self._get_value("Consumption") or []
        freq = self._get_value("DeliveryFrequency")
        recent = consumption[-3:] if isinstance(consumption, list) else []
        avg_liters = (
            sum(c.get("Liters", 0) for c in recent if isinstance(c, dict)) / len(recent)
            if recent else 0
        )
        return {
            "liters_per_month_avg": round(avg_liters, 1),
            "delivery_frequency_weeks": freq,
            "last_month": consumption[-1] if isinstance(consumption, list) and consumption else None,
        }
    

class MeiEdenStatusSensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:account-check"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "status")
        self._attr_name = "סטטוס לקוח"

    @property
    def native_value(self):
        status = self._get_value("Status")
        if not status:
            return "לא ידוע"
        mapping = {"001": "פעיל", "002": "מושעה", "003": "סגור"}
        return mapping.get(str(status), str(status))


class MeiEdenAddressSensor(MeiEdenBaseSensor):
    _attr_icon = "mdi:home-map-marker"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "address")
        self._attr_name = "כתובת משלוח"

    def _get_delivery_address(self) -> dict | None:
        data = self.coordinator.data or {}
        customer_data = data.get("dashboard", {}).get("customer", {})
        addresses = customer_data.get("addresses", [])
        
        if not isinstance(addresses, list) or not addresses:
            return None
            
        for addr in addresses:
            if isinstance(addr, dict) and addr.get("address_type") == "delivery":
                return addr
        for addr in addresses:
            if isinstance(addr, dict):
                return addr
        return None

    @property
    def native_value(self):
        addr = self._get_delivery_address()
        if not addr:
            return "לא נמצאה כתובת"
            
        parts = [
            addr.get("address1"),
            addr.get("house_number"),
            addr.get("city"),
        ]
        val = ", ".join(p.strip() for p in parts if p and isinstance(p, str) and p.strip())
        return val if val else "לא נמצאה כתובת"


class MeiEdenUrgentDeliverySensor(MeiEdenBaseSensor):
    """תאריך משלוח דחוף הקרוב ביותר (אם קיים)."""
    _attr_icon = "mdi:truck-alert"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "urgent_delivery")
        self._attr_name = "משלוח דחוף"

    @property
    def native_value(self):
        urgent: list = self._get_value("UrgentDeliveryDates") or []
        if not urgent:
            return None
        dt = _parse_dt(urgent[0])
        return dt.date() if dt else None

    @property
    def extra_state_attributes(self):
        urgent: list = self._get_value("UrgentDeliveryDates") or []
        return {
            "all_urgent_dates": [
                _parse_dt(d).date().isoformat() if _parse_dt(d) else d
                for d in urgent
            ],
            "count": len(urgent),
        }


class MeiEdenLastInvoiceSensor(MeiEdenBaseSensor):
    """סכום החשבונית האחרונה + קישור ל-PDF."""
    _attr_icon = "mdi:receipt-text"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = ILS

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "last_invoice")
        self._attr_name = "חשבונית אחרונה"

    def _latest_invoice(self) -> dict | None:
        inv_list = self._get_section("com-statements", "invoice_list")
        if isinstance(inv_list, list) and inv_list:
            return inv_list[0]
        return None

    @property
    def native_value(self):

        data = self.coordinator.data or {}
        # חיפוש רב-שלבי בתוך ה-dashboard
        sections = data.get("dashboard", {}).get("sections", {})
        statements = sections.get("com-statements", {})
        

        if statements and "last_invoice_amount" in statements:
            return float(statements.get("last_invoice_amount", 0))
            
        # אם לא קיים, תחזיר 0 כדי לא לקרוס
        return 0.0

    @property
    def extra_state_attributes(self):
        inv = self._latest_invoice() or {}
        dt = _parse_dt(inv.get("date"))
        pay_dt = _parse_dt(inv.get("pay_date"))
        return {
            "date": dt.date().isoformat() if dt else None,
            "pay_date": pay_dt.date().isoformat() if pay_dt else None,
            "status": inv.get("status"),
            "is_paid": inv.get("status") == "Paid",
            "vat": inv.get("vat_value"),
            "net": inv.get("net_value"),
            "pdf_url": inv.get("download_pdf_url"),
            "series": inv.get("series"),
            "reference": inv.get("reference"),
        }


class MeiEdenOverdueSensor(MeiEdenBaseSensor):
    """חוב בפיגור."""
    _attr_icon = "mdi:alert-circle"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = ILS

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "overdue")
        self._attr_name = "חוב בפיגור"

    @property
    def native_value(self):
        val = self._get_section("com-statements", "overdue_amount")
        try:
            return float(val) if val is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @property
    def extra_state_attributes(self):
        statements = self._get_section("com-statements") or {}
        return {
            "current_balance": statements.get("current_balance"),
            "next_payment_date": statements.get("next_payment_date") or None,
            "account_message": statements.get("account_message") or None,
        }


class MeiEdenEquipmentNameSensor(MeiEdenBaseSensor):
    """שם ודגם הבר מים המותקן."""
    _attr_icon = "mdi:water-pump"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "equipment_name")
        self._attr_name = "דגם בר מים"

    def _first_equipment(self) -> dict | None:
        eq = self._get_section("com-equipment")
        if isinstance(eq, list) and eq:
            return eq[0]
        return None

    @property
    def native_value(self):
        eq = self._first_equipment()
        return eq.get("Name") if eq else None

    @property
    def extra_state_attributes(self):
        eq = self._first_equipment() or {}
        return {
            "serial_number": eq.get("SerialNumber"),
            "business_line": eq.get("BusinessLine"),
            "image_url": eq.get("Image"),
            "product_url": eq.get("Url"),
            "active": eq.get("ActiveStatus"),
            "equipment_id": eq.get("Id"),
        }


class MeiEdenEquipmentInstallDateSensor(MeiEdenBaseSensor):
    """תאריך התקנת הבר מים + ימים מאז."""
    _attr_icon = "mdi:calendar-check"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "equipment_install")
        self._attr_name = "תאריך התקנת ציוד"

    def _first_equipment(self) -> dict | None:
        eq = self._get_section("com-equipment")
        if isinstance(eq, list) and eq:
            return eq[0]
        return None

    @property
    def native_value(self):
        eq = self._first_equipment()
        if not eq:
            return None
        dt = _parse_dt(eq.get("InstallDate"))
        return dt.date() if dt else None

    @property
    def extra_state_attributes(self):
        eq = self._first_equipment() or {}
        install_dt = _parse_dt(eq.get("InstallDate"))
        days_since = None
        if install_dt:
            days_since = (datetime.now() - install_dt).days
        return {
            "days_since_install": days_since,
            "replacement_date": (
                _parse_dt(eq.get("ReplacementDate")).date().isoformat()
                if _parse_dt(eq.get("ReplacementDate")) else None
            ),
            "return_date": eq.get("ReturnDate"),
        }


class MeiEdenEquipmentOwnershipSensor(MeiEdenBaseSensor):
    """האם הציוד בשכירות או קנוי."""
    _attr_icon = "mdi:tag"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "equipment_ownership")
        self._attr_name = "סוג בעלות ציוד"

    def _first_equipment(self) -> dict | None:
        eq = self._get_section("com-equipment")
        if isinstance(eq, list) and eq:
            return eq[0]
        return None

    @property
    def native_value(self):
        eq = self._first_equipment()
        if not eq:
            return None
        code = eq.get("RentalOrPurchase")
        return {1: "שכירות", 2: "קנייה"}.get(code, str(code))


class MeiEdenCustomerNameSensor(MeiEdenBaseSensor):
    """שם מלא של בעל החשבון."""
    _attr_icon = "mdi:account"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "customer_name")
        self._attr_name = "שם לקוח"

    @property
    def native_value(self):
        addr = self._get_value("InvoiceAddress") or {}
        first = addr.get("FirstName", "")
        last = addr.get("LastName", "")
        full = f"{first} {last}".strip()
        return full or None


class MeiEdenIsPackageSensor(MeiEdenBaseSensor):
    """האם הלקוח במסלול חבילה קבועה."""
    _attr_icon = "mdi:package-variant"

    def __init__(self, coordinator, customer_number):
        super().__init__(coordinator, customer_number, "is_package")
        self._attr_name = "מסלול חבילה"

    @property
    def native_value(self):
        is_pkg = self._get_value("IsPackage")
        if is_pkg is None:
            return "לא ידוע"
        return "חבילה קבועה" if is_pkg else "הזמנה רגילה"

    @property
    def extra_state_attributes(self):
        return {
            "raw": self._get_value("IsPackage"),
            "number_of_employees": self._get_value("NumberOfEmployees"),
            "pay_type_code": self._get_value("PayTypeCode"),
            "minimum_order_date": self._get_value("MinimumDateForOrder"),
        }