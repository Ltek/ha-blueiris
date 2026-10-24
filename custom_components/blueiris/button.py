"""
Support for Blue Iris buttons.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/button.blueiris/
"""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api.blue_iris_api import BlueIrisCommandError
from .helpers.const import *
from .models.base_entity import BlueIrisEntity, async_setup_base_entry
from .models.entity_data import EntityData

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]

CURRENT_DOMAIN = DOMAIN_BUTTON


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the BlueIris Button."""
    await async_setup_base_entry(
        hass, config_entry, async_add_devices, CURRENT_DOMAIN, get_button
    )


async def async_unload_entry(_hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {CURRENT_DOMAIN}: {config_entry}")

    return True


def get_button(hass: HomeAssistant, host: str, entity: EntityData):
    button = BlueIrisResetButton()
    button.initialize(hass, host, entity, CURRENT_DOMAIN)
    button._attr_device_class = entity.details.get(ENTITY_BUTTON_DEVICE_CLASS)

    return button


class BlueIrisResetButton(ButtonEntity, BlueIrisEntity):
    """Resets (reconnects) a camera, same as the reset_camera service."""

    @property
    def icon(self):
        return self.entity.icon

    async def async_press(self) -> None:
        try:
            await self.api.reset_camera(self.entity.id)
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex
