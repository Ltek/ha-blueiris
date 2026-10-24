import logging
import sys

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..managers.home_assistant import BlueIrisHomeAssistant
from ..managers.password_manager import PasswordManager
from .const import *
from .log_level import set_log_level

_LOGGER = logging.getLogger(__name__)


def clear_ha(hass: HomeAssistant, entry_id):
    if DATA_BLUEIRIS not in hass.data:
        hass.data[DATA_BLUEIRIS] = {}

    del hass.data[DATA_BLUEIRIS][entry_id]


def get_ha(hass: HomeAssistant, entry_id):
    ha_data = hass.data.get(DATA_BLUEIRIS, {})
    ha = ha_data.get(entry_id)

    return ha


async def async_set_ha(hass: HomeAssistant, entry: ConfigEntry):
    try:
        if DATA_BLUEIRIS not in hass.data:
            hass.data[DATA_BLUEIRIS] = {}

        if PASSWORD_MANAGER_BLUEIRIS not in hass.data:
            hass.data[PASSWORD_MANAGER_BLUEIRIS] = PasswordManager(hass)

        password_manager = hass.data[PASSWORD_MANAGER_BLUEIRIS]

        instance = BlueIrisHomeAssistant(hass, password_manager)

        await instance.async_init(entry)

        hass.data[DATA_BLUEIRIS][entry.entry_id] = instance
    except Exception as ex:
        exc_type, exc_obj, tb = sys.exc_info()
        line_number = tb.tb_lineno

        _LOGGER.error(f"Failed to async_set_ha, error: {ex}, line: {line_number}")


async def handle_log_level(hass: HomeAssistant, entry: ConfigEntry):
    """Apply the 'Default on Startup' level from the options.

    Default leaves Home Assistant's logging setup alone. Set directly on the
    logger, so it works without the logger integration in configuration.yaml.
    """
    log_level = entry.options.get(CONF_LOG_LEVEL, LOG_LEVEL_DEFAULT)

    if log_level not in LOG_LEVEL_SELECT_OPTIONS:
        return

    set_log_level(log_level)
    _LOGGER.debug(f"Log level set to {log_level} (Default on Startup)")
