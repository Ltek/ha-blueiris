"""
Support for Blue Iris select entities (log level on the server device).
"""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .helpers.log_level import set_log_level
from .helpers.const import *
from .models.base_entity import BlueIrisEntity, async_setup_base_entry
from .models.entity_data import EntityData

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]

CURRENT_DOMAIN = DOMAIN_SELECT


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the BlueIris Select."""
    await async_setup_base_entry(
        hass, config_entry, async_add_devices, CURRENT_DOMAIN, get_select
    )


async def async_unload_entry(_hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {CURRENT_DOMAIN}: {config_entry}")

    return True


def get_select(hass: HomeAssistant, host: str, entity: EntityData):
    select = BlueIrisLogLevelSelect()
    select.initialize(hass, host, entity, CURRENT_DOMAIN)

    return select


class BlueIrisLogLevelSelect(SelectEntity, BlueIrisEntity):
    """The integration's log level, as currently in effect.

    Changes apply at once and are not saved: the next start uses the
    options' 'Default on Startup' level.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = LOG_LEVEL_SELECT_OPTIONS

    @property
    def current_option(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon

    async def async_select_option(self, option: str) -> None:
        set_log_level(option)
        _LOGGER.info(f"Log level changed to {option}")

        self.entity.state = option
        self.async_write_ha_state()
