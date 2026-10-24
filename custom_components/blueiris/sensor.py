"""
Support for Blue Iris sensors.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blueiris/
"""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .helpers.const import *
from .models.base_entity import BlueIrisEntity, async_setup_base_entry
from .models.entity_data import EntityData

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]

CURRENT_DOMAIN = DOMAIN_SENSOR


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the BlueIris Sensor."""
    await async_setup_base_entry(
        hass, config_entry, async_add_devices, CURRENT_DOMAIN, get_sensor
    )


async def async_unload_entry(_hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {CURRENT_DOMAIN}: {config_entry}")

    return True


def get_sensor(hass: HomeAssistant, host: str, entity: EntityData):
    sensor = BlueIrisSensor()
    sensor.initialize(hass, host, entity, CURRENT_DOMAIN)

    # Fixed per sensor type, set once like the other platforms do
    details = entity.details
    sensor._attr_device_class = details.get(ENTITY_SENSOR_DEVICE_CLASS)
    sensor._attr_native_unit_of_measurement = details.get(ENTITY_SENSOR_UNIT)
    sensor._attr_suggested_unit_of_measurement = details.get(
        ENTITY_SENSOR_SUGGESTED_UNIT
    )
    sensor._attr_options = details.get(ENTITY_SENSOR_OPTIONS)
    sensor._attr_entity_category = details.get(ENTITY_SENSOR_CATEGORY)

    return sensor


class BlueIrisSensor(SensorEntity, BlueIrisEntity):
    """BlueIris server-level sensor."""

    @property
    def native_value(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon
