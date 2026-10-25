"""
Support for Blue Iris.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/blueiris/
"""
from datetime import datetime, timezone
import logging
import sys
from typing import Optional

from cryptography.fernet import InvalidToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EntityRegistry, async_get
from homeassistant.helpers.event import async_track_time_interval

from ..api.blue_iris_api import BlueIrisApi
from ..helpers.advanced_configurations_generator import AdvancedConfigurationGenerator
from ..helpers.const import *
from ..models.config_data import ConfigData
from .auto_reset_manager import AutoResetManager
from .stream_monitor import StreamMonitor
from .configuration_manager import ConfigManager
from .device_manager import DeviceManager
from .entity_manager import EntityManager
from .password_manager import PasswordManager
from .storage_manager import StorageManager

_LOGGER = logging.getLogger(__name__)


class BlueIrisHomeAssistant:
    def __init__(self, hass: HomeAssistant, password_manager: PasswordManager):
        self._hass = hass

        self._remove_async_track_time = None

        self._is_initialized = False
        self._is_updating = False

        self._entity_registry = None

        self._api = None
        self._entity_manager = None
        self._device_manager = None
        self._storage_manager = None
        self._auto_reset_manager: Optional[AutoResetManager] = None
        self.stream_monitor: Optional[StreamMonitor] = None
        self._last_motion_refresh: Optional[datetime] = None
        # Blue Iris log: newest entry time read, and the last reported entry
        self._log_after: Optional[int] = None
        self._log_seen: set = set()
        self.last_log_entry: Optional[dict] = None
        self._config_generator: Optional[AdvancedConfigurationGenerator] = None

        self._config_manager = ConfigManager(password_manager)

    @property
    def api(self) -> BlueIrisApi:
        return self._api

    @property
    def entity_manager(self) -> EntityManager:
        return self._entity_manager

    @property
    def device_manager(self) -> DeviceManager:
        return self._device_manager

    @property
    def auto_reset_manager(self) -> Optional[AutoResetManager]:
        return self._auto_reset_manager

    @property
    def entity_registry(self) -> EntityRegistry:
        return self._entity_registry

    @property
    def config_manager(self) -> ConfigManager:
        return self._config_manager

    @property
    def storage_manager(self) -> StorageManager:
        return self._storage_manager

    @property
    def config_data(self) -> Optional[ConfigData]:
        if self._config_manager is not None:
            return self._config_manager.data

        return None

    async def async_init(self, entry: ConfigEntry):
        try:
            self._storage_manager = StorageManager(self._hass)

            await self._config_manager.update(entry)

            self._api = BlueIrisApi(self._hass, self._config_manager)
            self._entity_manager = EntityManager(self._hass, self)
            self._device_manager = DeviceManager(self._hass, self)
            self._config_generator = AdvancedConfigurationGenerator(self._hass, self)
            self._auto_reset_manager = AutoResetManager(self._hass, self)
            self.stream_monitor = StreamMonitor(self._hass, self)

            self._entity_registry = async_get(self._hass)

            self._hass.loop.create_task(self._async_init())
        except InvalidToken:
            error_message = "Encryption key got corrupted, please remove the integration and re-add it"

            _LOGGER.error(error_message)

            data = await self._storage_manager.async_load_from_store()
            data.key = None
            await self._storage_manager.async_save_to_store(data)

            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {"title": DEFAULT_NAME, "message": error_message},
            )

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(f"Failed to async_init, error: {ex}, line: {line_number}")

    async def _async_init(self):
        await self._auto_reset_manager.async_load(
            self._config_manager.config_entry.entry_id
        )
        self.stream_monitor.apply_enabled()

        await self._hass.config_entries.async_forward_entry_setups(self._config_manager.config_entry, list(SIGNALS.keys()))

        self._is_initialized = True

        await self.async_update_entry()

    async def _update_entities(self, now):
        self._hass.async_create_task(self.async_update(now))

    async def async_update_entry(self, entry: ConfigEntry = None):
        update_config_manager = entry is not None

        if not update_config_manager:
            entry = self._config_manager.config_entry

            self._remove_async_track_time = async_track_time_interval(
                self._hass, self._update_entities, SCAN_INTERVAL
            )

        if not self._is_initialized:
            _LOGGER.debug(
                f"NOT INITIALIZED - Failed handling ConfigEntry change: {entry.as_dict()}"
            )
            return

        _LOGGER.debug(f"Handling ConfigEntry change: {entry.as_dict()}")

        if update_config_manager:
            await self._config_manager.update(entry)

        await self._api.initialize()

        await self.async_update(datetime.now())

        data = await self.storage_manager.async_load_from_store()
        integration_data = data.integrations.get(entry.title)

        if update_config_manager and integration_data is not None:
            if integration_data.generate_configuration_files:
                self._hass.loop.call_later(self._hass, 5, self.generate_config_files)

                integration_data.generate_configuration_files = False

            await self.storage_manager.async_save_to_store(data)

    async def async_remove(self, entry: ConfigEntry):
        _LOGGER.debug(f"Removing current integration - {entry.title}")

        if self._remove_async_track_time is not None:
            self._remove_async_track_time()
            self._remove_async_track_time = None

        if self.stream_monitor is not None:
            self.stream_monitor.stop()

        unload = self._hass.config_entries.async_forward_entry_unload

        for domain in SUPPORTED_DOMAINS:
            await unload(entry, domain)

        await self._device_manager.async_remove()

        _LOGGER.debug(f"Current integration ({entry.title}) removed")

    async def async_update(self, event_time):
        if not self._is_initialized:
            _LOGGER.debug(f"NOT INITIALIZED - Failed updating @{event_time}")
            return

        try:
            if self._is_updating:
                _LOGGER.debug(f"Skip updating @{event_time}")
                return

            _LOGGER.debug(f"Updating @{event_time}")

            self._is_updating = True

            await self._api.async_update()
            await self._async_refresh_motion_states()
            await self._async_read_log()

            self.entity_manager.update_camera_problems()
            await self._auto_reset_manager.async_evaluate()

            self.device_manager.update()
            self.entity_manager.update()

            await self.dispatch_all()
        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno
            _LOGGER.error(f"Failed to async_update, Error: {ex}, Line: {line_number}")

        self._is_updating = False

    async def _async_read_log(self):
        """Report new Blue Iris warnings / errors as blueiris_log events."""
        config_data = self.config_data

        if not config_data.log_events or not self._api.data.get("admin", False):
            return

        if self._log_after is None:
            # Start from now: older messages were before this start
            self._log_after = int(datetime.now(timezone.utc).timestamp())
            return

        entries = await self._api.load_log(self._log_after)
        min_level = LOG_MIN_LEVELS[config_data.log_min_level]
        seen = set()

        for entry in sorted(
            entries, key=lambda e: e.get("date", 0) if isinstance(e.get("date"), (int, float)) else 0
        ):
            date = entry.get("date")
            key = (date, entry.get("obj"), entry.get("msg"))
            seen.add(key)

            if isinstance(date, (int, float)):
                self._log_after = max(self._log_after, int(date))

            # Entries in the 'after' second come again next time
            if key in self._log_seen:
                continue

            level = entry.get("level")
            if not isinstance(level, int) or level not in (1, 2) or level < min_level:
                continue

            self.last_log_entry = entry
            self._hass.bus.async_fire(
                BI_LOG_EVENT,
                {
                    "level": BI_LOG_LEVELS.get(level, level),
                    "object": entry.get("obj"),
                    "message": entry.get("msg"),
                    "time": datetime.fromtimestamp(date, tz=timezone.utc).isoformat()
                    if isinstance(date, (int, float))
                    else None,
                    "count": entry.get("count"),
                },
            )

        # Only entries of the newest second can come back
        self._log_seen = {k for k in seen | self._log_seen if k[0] == self._log_after}

    async def _async_refresh_motion_states(self):
        """Read motion detection (not in camlist) every few minutes."""
        allowed = self.config_data.camera_controls[CAMERA_CONTROL_MOTION]

        if allowed == [] or not self._api.data.get("admin", False):
            return

        now = datetime.now(timezone.utc)
        last = self._last_motion_refresh
        if last is not None and now - last < MOTION_REFRESH_INTERVAL:
            return

        self._last_motion_refresh = now

        for camera in self._api.camera_list:
            if camera.is_physical and (allowed is None or camera.id in allowed):
                await self._api.load_motion_state(camera.id)

    async def delete_entity(self, domain, name):
        try:
            entity = self.entity_manager.get_entity(domain, name)
            device_name = entity.device_name
            unique_id = entity.unique_id

            self.entity_manager.delete_entity(domain, name)

            device_in_use = self.entity_manager.is_device_name_in_use(device_name)

            entity_id = self.entity_registry.async_get_entity_id(
                domain, DOMAIN, unique_id
            )
            self.entity_registry.async_remove(entity_id)

            if not device_in_use:
                await self.device_manager.delete_device(device_name)
        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(f"Failed to delete_entity, Error: {ex}, Line: {line_number}")

    async def dispatch_all(self):
        if not self._is_initialized:
            _LOGGER.debug("NOT INITIALIZED - Failed discovering components")
            return

        for domain in SUPPORTED_DOMAINS:
            signal = SIGNALS.get(domain)

            async_dispatcher_send(self._hass, signal)

    async def generate_config_files(self, _now):
        self._config_generator.generate()
