"""
Support for Blue Iris number entities (auto reset settings per camera).
"""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .helpers.const import *
from .models.base_entity import BlueIrisEntity, async_setup_base_entry
from .models.entity_data import EntityData

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]

CURRENT_DOMAIN = DOMAIN_NUMBER


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the BlueIris Number."""
    await async_setup_base_entry(
        hass, config_entry, async_add_devices, CURRENT_DOMAIN, get_number
    )


async def async_unload_entry(_hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {CURRENT_DOMAIN}: {config_entry}")

    return True


def get_number(hass: HomeAssistant, host: str, entity: EntityData):
    number = BlueIrisAutoResetNumber()
    number.initialize(hass, host, entity, CURRENT_DOMAIN)

    details = entity.details
    number._attr_native_min_value = details[ENTITY_NUMBER_MIN]
    number._attr_native_max_value = details[ENTITY_NUMBER_MAX]
    number._attr_native_step = details[ENTITY_NUMBER_STEP]
    number._attr_native_unit_of_measurement = details.get(ENTITY_NUMBER_UNIT)

    return number


class BlueIrisAutoResetNumber(NumberEntity, BlueIrisEntity):
    """Auto reset delay / attempts / interval for one camera.

    Stored by the integration and used from the next poll; no reload needed.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon

    async def async_set_native_value(self, value: float) -> None:
        key = self.entity.details[AUTO_RESET_SETTING]

        if key == AUTO_RESET_KEY_ATTEMPTS:
            value = int(round(value))

        self.ha.auto_reset_manager.set_camera_value(self.entity.id, key, value)

        self.entity.state = self.ha.auto_reset_manager.camera_settings(
            self.entity.id
        )[key]
        self.async_write_ha_state()

        self.entity_manager.update()
        await self.ha.dispatch_all()
