"""
Support for Blue Iris buttons.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/button.blueiris/
"""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
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
    if entity.type == CAMERA_CONTROL:
        button = BlueIrisCameraControlButton()
    elif entity.type == SERVER_CONTROL:
        button = BlueIrisServerButton()
    elif entity.type == RELOAD_BUTTON:
        button = BlueIrisReloadButton()
    else:
        button = BlueIrisResetButton()

    button.initialize(hass, host, entity, CURRENT_DOMAIN)
    button._attr_device_class = entity.details.get(ENTITY_BUTTON_DEVICE_CLASS)

    if entity.details.get(ENTITY_CONFIG_CATEGORY):
        button._attr_entity_category = EntityCategory.CONFIG

    return button


class BlueIrisCameraControlButton(ButtonEntity, BlueIrisEntity):
    """Snapshot to Database or Reboot."""

    @property
    def icon(self):
        return self.entity.icon

    async def async_press(self) -> None:
        key = self.entity.details[CAMERA_CONTROL_KEY]

        try:
            if key == CAMERA_CONTROL_SNAPSHOT:
                await self.api.snapshot_to_database(self.entity.id)
            else:
                await self.api.reboot_camera(self.entity.id)
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex


class BlueIrisReloadButton(ButtonEntity, BlueIrisEntity):
    """Reload the integration (same as Devices & Services -> Reload)."""

    @property
    def icon(self):
        return self.entity.icon

    async def async_press(self) -> None:
        entry_id = self.ha.config_manager.config_entry.entry_id
        _LOGGER.info("Reloading the Blue Iris integration")

        # The reload unloads this button too; don't wait for it here
        self.hass.async_create_task(self.hass.config_entries.async_reload(entry_id))


class BlueIrisServerButton(ButtonEntity, BlueIrisEntity):
    """Restart Blue Iris' web server or AI."""

    @property
    def icon(self):
        return self.entity.icon

    async def async_press(self) -> None:
        key = self.entity.details[SERVER_CONTROL_KEY]

        try:
            if key == SERVER_CONTROL_RESTART_WEB:
                await self.api.restart_web_server()
                # Its sessions end with it
                self.api.is_logged_in = False
            else:
                await self.api.restart_ai()
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex


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
