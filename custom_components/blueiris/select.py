"""
Support for Blue Iris select entities (log level on the server device).
"""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api.blue_iris_api import BlueIrisCommandError

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
    if entity.type == CAMERA_CONTROL:
        select = BlueIrisPauseSelect()
    elif entity.type == SERVER_CONTROL:
        select = BlueIrisShieldSelect()
    elif entity.type == STREAM_METHOD:
        select = BlueIrisStreamMethodSelect()
    else:
        select = BlueIrisLogLevelSelect()

    select.initialize(hass, host, entity, CURRENT_DOMAIN)

    return select


class BlueIrisStreamMethodSelect(SelectEntity, BlueIrisEntity):
    """How cameras build their stream URL; applies to running streams."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = STREAM_METHODS

    @property
    def current_option(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon

    async def async_select_option(self, option: str) -> None:
        self.ha.auto_reset_manager.set_stream_method(option)
        _LOGGER.info(f"Stream method set to {option}")

        self.entity.state = option
        self.async_write_ha_state()

        # Cameras pick it up and restart their running stream if needed
        self.entity_manager.update()
        await self.ha.dispatch_all()


class BlueIrisShieldSelect(SelectEntity, BlueIrisEntity):
    """Blue Iris' shield: Armed (green), Disarmed (red), Arming (yellow)."""

    _attr_options = list(SHIELD_OPTIONS)

    @property
    def current_option(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon

    async def async_select_option(self, option: str) -> None:
        try:
            await self.api.set_shield(SHIELD_OPTIONS[option])
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex

        await self.ha.async_update(None)


class BlueIrisPauseSelect(SelectEntity, BlueIrisEntity):
    """Pause a camera (recording, alerts) for a while, or resume it.

    Unknown while a timed pause set elsewhere is running; the remaining
    time is in the attributes.
    """

    _attr_options = list(PAUSE_OPTIONS)

    @property
    def current_option(self):
        return self.entity.state

    @property
    def icon(self):
        return self.entity.icon

    async def async_select_option(self, option: str) -> None:
        camera_id = self.entity.id

        try:
            # Timed values add to a running pause, so clear it first
            await self.api.set_camera_value(camera_id, "pause", 0)
            if PAUSE_OPTIONS[option] != 0:
                await self.api.set_camera_value(camera_id, "pause", PAUSE_OPTIONS[option])
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex

        if option in (PAUSE_OFF, PAUSE_INDEFINITELY):
            self.entity_manager.pause_choice.pop(camera_id, None)
        else:
            self.entity_manager.pause_choice[camera_id] = option

        await self.ha.async_update(None)


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
