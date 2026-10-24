"""Diagnostics support for Blue Iris."""
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .helpers import get_ha

TO_REDACT = {
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    "session",
    "session_id",
    "base_url",
    "license",
    "user",
    "latitude",
    "longitude",
    "stream_source",
    "still_image_url",
}

# Camera fields from camlist that help with stream / signal problems
CAMERA_FIELDS = [
    "optionValue",
    "optionDisplay",
    "type",
    "isEnabled",
    "isOnline",
    "isNoSignal",
    "isPaused",
    "isYellow",
    "FPS",
    "width",
    "height",
    "audio",
    "nNoSignal",
    "error",
    "group",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    ha = get_ha(hass, entry.entry_id)
    api = ha.api if ha is not None else None

    result: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "api": None,
        "cameras": [],
        "entities": {},
    }

    if api is None:
        return result

    login_data = getattr(api, "data", {}) or {}
    status = getattr(api, "status", {}) or {}

    result["api"] = {
        "is_logged_in": getattr(api, "is_logged_in", None),
        "has_session": getattr(api, "session_id", None) is not None,
        # Present when the connection health sensor is installed
        "connection_state": getattr(api, "connection_state", None),
        "consecutive_failures": getattr(api, "consecutive_failures", None),
        "server": async_redact_data(
            {
                "version": login_data.get("version"),
                "admin": login_data.get("admin"),
                "system name": login_data.get("system name"),
                "profiles": login_data.get("profiles"),
                "schedules": login_data.get("schedules"),
                "streams": login_data.get("streams"),
            },
            TO_REDACT,
        ),
        "status": async_redact_data(dict(status), TO_REDACT),
    }

    for camera in getattr(api, "camera_list", []) or []:
        data = camera.data or {}
        result["cameras"].append({k: data.get(k) for k in CAMERA_FIELDS if k in data})

    entity_manager = ha.entity_manager
    if entity_manager is not None:
        for domain, entities in entity_manager.entities.items():
            result["entities"][domain] = sorted(
                entity.name for entity in entities.values()
            )

    return result
