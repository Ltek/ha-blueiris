from datetime import datetime, timedelta, timezone
import logging
import re
import sys
from typing import Optional

from homeassistant.components.camera import DEFAULT_CONTENT_TYPE
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.components.stream import DOMAIN as DOMAIN_STREAM
from homeassistant.const import CONF_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import slugify

from ..api.blue_iris_api import BlueIrisApi
from ..helpers.log_level import get_log_level
from ..helpers.const import *
from ..models.camera_data import CameraData
from ..models.config_data import ConfigData
from ..models.entity_data import EntityData
from .configuration_manager import ConfigManager
from .device_manager import DeviceManager

_LOGGER = logging.getLogger(__name__)


def _parse_uptime(value) -> Optional[int]:
    """Convert Blue Iris' D:HH:MM:SS uptime to seconds."""
    if not isinstance(value, str):
        return None

    parts = value.strip().split(":")

    if len(parts) != 4:
        return None

    try:
        days, hours, minutes, seconds = map(int, parts)
    except ValueError:
        return None

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def utcnow() -> datetime:
    """Current time; one place so tests can control the clock."""
    return datetime.now(timezone.utc)


def get_camera_problem(camera: CameraData) -> Optional[str]:
    """Return why a camera needs attention, or None when it is fine.

    Disabled and paused cameras are left alone on purpose.
    """
    data = camera.data

    if not data.get("isEnabled", True) or data.get("isPaused", False):
        return None

    if data.get("isNoSignal", False):
        return PROBLEM_NO_SIGNAL

    if not camera.is_online:
        return PROBLEM_OFFLINE

    fps = data.get("FPS")
    if isinstance(fps, (int, float)) and fps < PROBLEM_MIN_FPS:
        return PROBLEM_STALLED

    return None


_SIZE_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}


def parse_number(value) -> Optional[float]:
    """A number from Blue Iris, which may come as '45%', '7.5' or 7.5."""
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))

    return None if match is None else float(match.group(0))


def parse_size_gb(value) -> Optional[float]:
    """A size in GB (GiB) from '1.23 TB', '512G', '850 MB', or bytes."""
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return round(value / 1024**3, 2)

    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([KMGTP]?)I?B?", str(value).upper())
    if match is None:
        return None

    size = float(match.group(1)) * _SIZE_UNITS[match.group(2)]

    # A bare number without a unit is taken as bytes
    return round(size / 1024**3, 2)


def _get_camera_binary_sensor_key(topic, event_type):
    key = f"{topic}_{event_type}".lower()

    return key


class EntityManager:
    hass: HomeAssistant
    ha = None
    entities: dict
    domain_component_manager: dict
    mqtt_states: dict

    def __init__(self, hass, ha):
        self.hass = hass
        self.ha = ha
        self.domain_component_manager = {}
        self.entities = {}
        self.mqtt_states = {}
        # Problem state per camera id, refreshed once per poll by
        # update_camera_problems (MQTT-driven updates reuse it)
        self.problem_data_fresh = False
        self.camera_problems = {}
        self.problem_since = {}
        self.last_problem = {}
        self.last_problem_since = {}
        # camera id -> last Pause choice, to show a timed pause by its name
        self.pause_choice = {}

    @property
    def entity_registry(self) -> EntityRegistry:
        return self.ha.entity_registry

    @property
    def config_data(self) -> ConfigData:
        return self.ha.config_data

    @property
    def config_manager(self) -> ConfigManager:
        return self.ha.config_manager

    @property
    def api(self) -> BlueIrisApi:
        return self.ha.api

    @property
    def device_manager(self) -> DeviceManager:
        return self.ha.device_manager

    @property
    def integration_title(self) -> str:
        return self.config_manager.config_entry.title

    @property
    def system_device_name(self) -> str:
        return self.device_manager.get_system_device_name()

    def set_domain_component(self, domain, async_add_entities, component):
        self.domain_component_manager[domain] = {
            "async_add_entities": async_add_entities,
            "component": component,
        }

    def is_device_name_in_use(self, device_name):
        result = False

        for entity in self.get_all_entities():
            if entity.device_name == device_name:
                result = True
                break

        return result

    def get_all_entities(self) -> list[EntityData]:
        entities = []
        for domain in self.entities:
            for name in self.entities[domain]:
                entity = self.entities[domain][name]

                entities.append(entity)

        return entities

    def check_domain(self, domain):
        if domain not in self.entities:
            self.entities[domain] = {}

    def get_entities(self, domain) -> dict[str, EntityData]:
        self.check_domain(domain)

        return self.entities[domain]

    def get_entity(self, domain, name) -> Optional[EntityData]:
        entities = self.get_entities(domain)
        entity = entities.get(name)

        return entity

    def get_entity_status(self, domain, name):
        entity = self.get_entity(domain, name)

        status = ENTITY_STATUS_EMPTY if entity is None else entity.status

        return status

    def set_entity_status(self, domain, name, status):
        if domain in self.entities and name in self.entities[domain]:
            self.entities[domain][name].status = status

    def delete_entity(self, domain, name):
        if domain in self.entities and name in self.entities[domain]:
            del self.entities[domain][name]

    def set_entity(self, domain, name, data: EntityData):
        try:
            self.check_domain(domain)

            self.entities[domain][name] = data
        except Exception as ex:
            self.log_exception(
                ex, f"Failed to set_entity, domain: {domain}, name: {name}"
            )

    def get_mqtt_state(self, topic, event_type, default=False):
        key = _get_camera_binary_sensor_key(topic, event_type)

        state = self.mqtt_states.get(key, default)

        return state

    def set_mqtt_state(self, topic, event_type, value):
        key = _get_camera_binary_sensor_key(topic, event_type)

        self.mqtt_states[key] = value

    def create_components(self):
        config_data = self.config_data
        available_camera = self.api.camera_list
        available_profiles = self.api.data.get("profiles", [])
        available_schedules = self.api.data.get("schedules", [])
        is_admin = self.api.data.get("admin", False)
        allowed_profile = config_data.allowed_profile
        allowed_schedule = config_data.allowed_schedule
        system_device_name = self.system_device_name

        # Each list filters only its own switches; an empty profile list
        # must not hide the schedule switches (or the other way round)
        if is_admin:
            for profile_name in available_profiles:
                profile_id = available_profiles.index(profile_name)

                if allowed_profile is None or str(profile_id) in allowed_profile:
                    self.generate_profile_switch(
                        profile_id, profile_name, system_device_name
                    )
            for schedule_name in available_schedules:
                schedule_id = available_schedules.index(schedule_name)

                if allowed_schedule is None or str(schedule_id) in allowed_schedule:
                    self.generate_schedule_switch(schedule_name, system_device_name)

        self.generate_server_sensors(system_device_name)

        self.generate_auto_reset_server_switches(system_device_name, is_admin)
        self.generate_log_level_select(system_device_name)

        mqtt_binary_sensors = []
        for camera in available_camera:
            self.generate_camera_component(camera)
            self.generate_camera_problem_sensor(camera)
            self.generate_camera_reset_button(camera, is_admin)
            self.generate_camera_auto_reset_entities(camera, is_admin)
            self.generate_camera_controls(camera, is_admin)
            self.generate_camera_sensors(camera)
            current_mqtt_binary_sensors = self.generate_camera_binary_sensors(camera)

            mqtt_binary_sensors.extend(current_mqtt_binary_sensors)

        if len(mqtt_binary_sensors) > 0:
            self.generate_main_binary_sensor()

    def update(self):
        self.hass.async_create_task(self._async_update())

    async def _async_update(self):
        step = "Mark as ignore"
        try:
            entities_to_delete = []

            for entity in self.get_all_entities():
                entities_to_delete.append(entity.unique_id)

            step = "Create components"

            self.create_components()

            step = "Start updating"

            for domain in SIGNALS:
                step = f"Start updating domain {domain}"

                entities_to_add = []
                domain_component_manager = self.domain_component_manager[domain]
                domain_component = domain_component_manager["component"]
                async_add_entities = domain_component_manager["async_add_entities"]

                entities = dict(self.get_entities(domain))

                for entity_key in entities:
                    step = f"Start updating {domain} -> {entity_key}"

                    entity = entities[entity_key]

                    entity_id = self.entity_registry.async_get_entity_id(
                        domain, DOMAIN, entity.unique_id
                    )

                    if entity.status == ENTITY_STATUS_CREATED:
                        entity_item = self.entity_registry.async_get(entity_id)

                        if entity.unique_id in entities_to_delete:
                            entities_to_delete.remove(entity.unique_id)

                        step = f"Mark as created - {domain} -> {entity_key}"

                        entity_component = domain_component(
                            self.hass, self.config_manager.config_entry.entry_id, entity
                        )

                        if entity_id is not None:
                            entity_id = self._fix_device_prefixed_entity_id(
                                domain, entity, entity_id
                            )
                            entity_component.entity_id = entity_id

                            state = self.hass.states.get(entity_id)

                            if state is None:
                                restored = True
                            else:
                                restored = state.attributes.get("restored", False)

                                if restored:
                                    _LOGGER.debug(
                                        f"Entity {entity.name} restored | {entity_id}"
                                    )

                            if restored:
                                if entity_item is None or not entity_item.disabled:
                                    entities_to_add.append(entity_component)
                        else:
                            # Suggest the ID from the entity's own name, which
                            # already contains the integration and camera name.
                            # Otherwise newer HA versions prefix the device
                            # name as well, giving e.g.
                            # binary_sensor.bi5_driveway_driveway_bi5_driveway_problem
                            entity_component.entity_id = (
                                f"{domain}.{slugify(entity.name)}"
                            )
                            entities_to_add.append(entity_component)

                        entity.status = ENTITY_STATUS_READY

                        if entity_item is not None:
                            entity.disabled = entity_item.disabled

                step = f"Add entities to {domain}"

                if len(entities_to_add) > 0:
                    async_add_entities(entities_to_add, True)

            if len(entities_to_delete) > 0:
                _LOGGER.debug(f"Following items will be deleted: {entities_to_delete}")

                for domain in SIGNALS:
                    entities = dict(self.get_entities(domain))

                    for entity_key in entities:
                        entity = entities[entity_key]
                        if entity.unique_id in entities_to_delete:
                            await self.ha.delete_entity(domain, entity.name)

        except Exception as ex:
            self.log_exception(ex, f"Failed to update, step: {step}")

    def _fix_device_prefixed_entity_id(
        self, domain, entity: EntityData, entity_id: str
    ) -> str:
        """Rename an entity ID that HA built as device name + entity name.

        Only an ID that is exactly that doubled form is renamed, so IDs the
        user chose are never touched.
        """
        device_name = self.device_manager.get(entity.device_name).get("name")

        if not device_name:
            return entity_id

        doubled = f"{domain}.{slugify(f'{device_name} {entity.name}')}"
        wanted = f"{domain}.{slugify(entity.name)}"

        if entity_id != doubled or entity_id == wanted:
            return entity_id

        if self.entity_registry.async_is_registered(wanted) or self.hass.states.get(
            wanted
        ):
            _LOGGER.debug(f"Not renaming {entity_id}, {wanted} is already in use")
            return entity_id

        _LOGGER.info(f"Renaming {entity_id} to {wanted}")
        self.entity_registry.async_update_entity(entity_id, new_entity_id=wanted)

        return wanted

    def get_profile_switch(
        self, profile_id, profile_name, system_device_name
    ) -> EntityData:
        entity = None

        try:
            current_profile = self.api.status.get("profile", 0)

            entity_name = (
                f"{self.integration_title} {ATTR_ADMIN_PROFILE} {profile_name}"
            )
            unique_id = f"{DOMAIN}-{DOMAIN_SWITCH}-{ATTR_ADMIN_PROFILE}-{entity_name}"

            state = current_profile == profile_id

            attributes = {ATTR_FRIENDLY_NAME: entity_name}

            entity = EntityData()

            entity.id = profile_id
            entity.unique_id = unique_id
            entity.name = entity_name
            entity.state = state
            entity.attributes = attributes
            entity.icon = DEFAULT_ICON
            entity.device_name = system_device_name
        except Exception as ex:
            self.log_exception(
                ex, f"Failed to get profile switch {profile_name} (#{profile_id})"
            )

        return entity

    def generate_profile_switch(self, profile_id, profile_name, system_device_name):
        try:
            entity = self.get_profile_switch(
                profile_id, profile_name, system_device_name
            )
            entity_name = entity.name

            self.set_entity(DOMAIN_SWITCH, entity_name, entity)
        except Exception as ex:
            self.log_exception(
                ex, f"Failed to generate profile switch {profile_name} (#{profile_id})"
            )

    def get_schedule_switch(self, schedule_name, system_device_name) -> EntityData:
        entity = None

        try:
            current_schedule = self.api.status.get("schedule", 0)

            entity_name = (
                f"{self.integration_title} {ATTR_ADMIN_SCHEDULE} {schedule_name}"
            )
            unique_id = f"{DOMAIN}-{DOMAIN_SWITCH}-{ATTR_ADMIN_SCHEDULE}-{entity_name}"

            state = current_schedule == schedule_name

            attributes = {ATTR_FRIENDLY_NAME: entity_name}

            entity = EntityData()

            entity.id = schedule_name
            entity.unique_id = unique_id
            entity.name = entity_name
            entity.state = state
            entity.attributes = attributes
            entity.icon = SCHEDULE_ICON
            entity.device_name = system_device_name
        except Exception as ex:
            self.log_exception(ex, f"Failed to get schedule switch {schedule_name}")

        return entity

    def generate_schedule_switch(self, schedule_name, system_device_name):
        try:
            entity = self.get_schedule_switch(schedule_name, system_device_name)
            entity_name = entity.name

            self.set_entity(DOMAIN_SWITCH, entity_name, entity)
        except Exception as ex:
            self.log_exception(
                ex, f"Failed to generate schedule switch {schedule_name} "
            )

    def get_connection_health_sensor(self, system_device_name) -> EntityData:
        entity_name = f"{self.integration_title} {SENSOR_CONNECTION_HEALTH_NAME}"
        unique_id = f"{DOMAIN}-{DOMAIN_SENSOR}-{entity_name}"

        api = self.api
        last_success_time = api.last_success_time

        attributes = {
            ATTR_FRIENDLY_NAME: entity_name,
            "last_update_success": api.last_update_success,
            "last_success_time": None
            if last_success_time is None
            else last_success_time.isoformat(),
            "consecutive_failures": api.consecutive_failures,
            "is_logged_in": api.is_logged_in,
            "bi_version": api.data.get("version"),
            "profile": api.status.get("profile"),
            "schedule": api.status.get("schedule"),
        }

        entity = EntityData()

        entity.unique_id = unique_id
        entity.name = entity_name
        entity.state = api.connection_state
        entity.attributes = attributes
        entity.icon = CONNECTION_HEALTH_ICON
        entity.device_name = system_device_name
        entity.type = SENSOR_CONNECTION_HEALTH_NAME
        entity.details = {
            ENTITY_SENSOR_DEVICE_CLASS: SensorDeviceClass.ENUM,
            ENTITY_SENSOR_OPTIONS: CONNECTION_STATES,
        }

        return entity

    def get_uptime_sensor(self, system_device_name) -> EntityData:
        entity_name = f"{self.integration_title} {SENSOR_UPTIME_NAME}"
        unique_id = f"{DOMAIN}-{DOMAIN_SENSOR}-{entity_name}"

        entity = EntityData()

        entity.unique_id = unique_id
        entity.name = entity_name
        entity.state = _parse_uptime(self.api.status.get("uptime"))
        entity.attributes = {ATTR_FRIENDLY_NAME: entity_name}
        entity.icon = UPTIME_ICON
        entity.device_name = system_device_name
        entity.type = SENSOR_UPTIME_NAME
        entity.details = {
            ENTITY_SENSOR_DEVICE_CLASS: SensorDeviceClass.DURATION,
            ENTITY_SENSOR_UNIT: UnitOfTime.SECONDS,
            ENTITY_SENSOR_SUGGESTED_UNIT: UnitOfTime.HOURS,
            ENTITY_SENSOR_CATEGORY: EntityCategory.DIAGNOSTIC,
        }

        return entity

    def is_problem_data_fresh(self) -> bool:
        """Only judge cameras on a successful poll of a settled server."""
        if self.api.connection_state != CONNECTION_STATE_CONNECTED:
            return False

        uptime = _parse_uptime(self.api.status.get("uptime"))

        return uptime is None or uptime >= PROBLEM_STARTUP_GRACE

    def update_camera_problems(self):
        """Work out each camera's problem once per poll."""
        fresh = self.is_problem_data_fresh()
        self.problem_data_fresh = fresh

        if not fresh:
            # Keep the last known problems and their start times; nothing is
            # judged until the data is fresh again
            return

        now = utcnow()
        seen = set()

        for camera in self.api.camera_list:
            if not camera.is_physical:
                continue

            seen.add(camera.id)
            problem = (
                get_camera_problem(camera)
                if self._problem_detection(camera.id)
                else None
            )

            if problem is None:
                self.camera_problems.pop(camera.id, None)
                self.problem_since.pop(camera.id, None)
                continue

            self.camera_problems[camera.id] = problem
            self.last_problem[camera.id] = problem

            if camera.id not in self.problem_since:
                self.problem_since[camera.id] = now
                self.last_problem_since[camera.id] = now

        for camera_id in list(self.camera_problems):
            if camera_id not in seen:
                self.camera_problems.pop(camera_id, None)
                self.problem_since.pop(camera_id, None)

    def _problem_detection(self, camera_id: str) -> bool:
        auto_reset = self.ha.auto_reset_manager
        return auto_reset is None or auto_reset.problem_detection(camera_id)

    def is_problem_sensor_allowed(self, camera: CameraData) -> bool:
        allowed = self.config_data.allowed_problem_sensor

        return camera.is_physical and (allowed is None or camera.id in allowed)

    def get_camera_problem_sensor(self, camera: CameraData) -> EntityData:
        device_name = self.device_manager.get_camera_device_name(camera)
        entity_name = f"{self.integration_title} {camera.name} {SENSOR_PROBLEM_NAME}"
        unique_id = f"{DOMAIN}-{DOMAIN_BINARY_SENSOR}-{entity_name}"

        data_fresh = self.problem_data_fresh
        problem = self.camera_problems.get(camera.id) if data_fresh else None
        since = self.problem_since.get(camera.id)
        data = camera.data

        attributes = {
            ATTR_FRIENDLY_NAME: entity_name,
            "camera_id": camera.id,
            ATTR_PROBLEM_DETECTION: self._problem_detection(camera.id),
            "reason": problem,
            "since": None if since is None else since.isoformat(),
            "fps": data.get("FPS"),
            "is_online": camera.is_online,
            "no_signal": data.get("isNoSignal"),
            "no_signal_count": data.get("nNoSignal"),
            "error": data.get("error"),
        }

        auto_reset = self.ha.auto_reset_manager
        if auto_reset is not None and self.api.data.get("admin", False):
            attributes.update(auto_reset.status(camera.id))

        entity = EntityData()

        entity.id = camera.id
        entity.unique_id = unique_id
        entity.name = entity_name
        entity.state = problem is not None
        entity.attributes = attributes
        entity.icon = PROBLEM_ICON
        entity.device_name = device_name
        # Lets the server's Alerts sensor list cameras with a problem
        entity.event = SENSOR_PROBLEM_NAME
        entity.type = SENSOR_PROBLEM_NAME
        entity.binary_sensor_device_class = BinarySensorDeviceClass.PROBLEM
        entity.details = {ENTITY_AVAILABLE: data_fresh}

        return entity

    def generate_camera_problem_sensor(self, camera: CameraData):
        try:
            if not self.is_problem_sensor_allowed(camera):
                return

            entity = self.get_camera_problem_sensor(camera)
            self.set_entity(DOMAIN_BINARY_SENSOR, entity.name, entity)

            device_name = self.device_manager.get_camera_device_name(camera)
            name = f"{self.integration_title} {camera.name} {PROBLEM_DETECTION_NAME}"
            switch = self._config_entity(
                DOMAIN_SWITCH,
                name,
                camera.id,
                device_name,
                PROBLEM_DETECTION_SWITCH,
                self._problem_detection(camera.id),
                PROBLEM_DETECTION_ICON,
                {},
            )
            self.set_entity(DOMAIN_SWITCH, name, switch)
        except Exception as ex:
            self.log_exception(ex, f"Failed to generate problem sensor for {camera}")

    def _config_entity(
        self, domain, name, unique_suffix, device_name, entity_type, state, icon, details
    ) -> EntityData:
        entity = EntityData()

        entity.id = unique_suffix
        entity.unique_id = f"{DOMAIN}-{domain}-{name}"
        entity.name = name
        entity.state = state
        entity.attributes = {ATTR_FRIENDLY_NAME: name}
        entity.icon = icon
        entity.device_name = device_name
        entity.type = entity_type
        entity.details = details

        return entity

    def generate_log_level_select(self, system_device_name):
        try:
            name = f"{self.integration_title} {LOG_LEVEL_NAME}"
            entity = self._config_entity(
                DOMAIN_SELECT,
                name,
                None,
                system_device_name,
                LOG_LEVEL_NAME,
                get_log_level(),
                LOG_LEVEL_ICON,
                {},
            )
            self.set_entity(DOMAIN_SELECT, name, entity)
        except Exception as ex:
            self.log_exception(ex, "Failed to generate log level select")

    def get_pause_option(self, camera: CameraData) -> Optional[str]:
        pause = camera.data.get("pause", 0)

        if not isinstance(pause, (int, float)) or pause == 0:
            self.pause_choice.pop(camera.id, None)
            return PAUSE_OFF

        if pause < 0:
            return PAUSE_INDEFINITELY

        # A timed pause: the choice made here, if it was made here
        return self.pause_choice.get(camera.id)

    def generate_camera_controls(self, camera: CameraData, is_admin):
        try:
            # camconfig needs admin rights; groups have no settings of their own
            if not is_admin or not camera.is_physical:
                return

            device_name = self.device_manager.get_camera_device_name(camera)
            data = camera.data

            for key, (label, domain, icon, is_config) in CAMERA_CONTROL_ENTITIES.items():
                allowed = self.config_data.camera_controls[key]

                if allowed is not None and camera.id not in allowed:
                    continue

                attributes = {}

                if key == CAMERA_CONTROL_ENABLE:
                    state = bool(data.get("isEnabled", True))
                elif key == CAMERA_CONTROL_MANREC:
                    state = bool(data.get("isManRec", False))
                elif key == CAMERA_CONTROL_MOTION:
                    state = self.api.motion_states.get(camera.id)
                elif key == CAMERA_CONTROL_PAUSE:
                    state = self.get_pause_option(camera)
                    remaining = data.get("pause", 0)
                    seconds = remaining if isinstance(remaining, (int, float)) else 0
                    attributes = {
                        "paused": bool(data.get("isPaused", seconds != 0)),
                        "remaining": seconds if seconds > 0 else None,
                        "until": (utcnow() + timedelta(seconds=seconds)).isoformat()
                        if seconds > 0
                        else None,
                    }
                else:
                    state = None

                name = f"{self.integration_title} {camera.name} {label}"
                details = {
                    CAMERA_CONTROL_KEY: key,
                    ENTITY_CONFIG_CATEGORY: is_config,
                }
                if key == CAMERA_CONTROL_REBOOT:
                    details[ENTITY_BUTTON_DEVICE_CLASS] = ButtonDeviceClass.RESTART

                entity = self._config_entity(
                    domain, name, camera.id, device_name, CAMERA_CONTROL, state, icon, details
                )
                entity.attributes.update(attributes)

                self.set_entity(domain, name, entity)
        except Exception as ex:
            self.log_exception(ex, f"Failed to generate camera controls for {camera}")

    def _camera_sensor_allowed(self, key, camera: CameraData) -> bool:
        allowed = self.config_data.camera_sensors[key]
        return camera.is_physical and (allowed is None or camera.id in allowed)

    @staticmethod
    def _bitrate_kbps(data: dict, *keys) -> Optional[float]:
        for key in keys:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Blue Iris sends bytes per second
                return round(value * 8 / 1000, 1)
        return None

    @staticmethod
    def get_last_alert_time(data: dict) -> Optional[datetime]:
        """alertutc (seconds) or lastalertutc (milliseconds)."""
        value = data.get("alertutc")
        scale = 1

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            value = data.get("lastalertutc")
            scale = 1000

        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            return None

        return datetime.fromtimestamp(value / scale, tz=timezone.utc)

    def generate_camera_sensors(self, camera: CameraData):
        try:
            device_name = self.device_manager.get_camera_device_name(camera)
            data = camera.data
            base = f"{self.integration_title} {camera.name}"
            diagnostic = {ENTITY_SENSOR_CATEGORY: EntityCategory.DIAGNOSTIC}
            rate = {
                **diagnostic,
                ENTITY_SENSOR_DEVICE_CLASS: SensorDeviceClass.DATA_RATE,
                ENTITY_SENSOR_UNIT: UnitOfDataRate.KILOBITS_PER_SECOND,
                ENTITY_SENSOR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            }
            sensors = []

            if self._camera_sensor_allowed(CAMERA_SENSOR_BITRATE, camera):
                sensors.append(
                    (
                        "Bitrate",
                        self._bitrate_kbps(data, "BPS", "bps"),
                        "mdi:speedometer",
                        rate,
                        {
                            "fps": data.get("FPS", data.get("fps")),
                            "width": data.get("width"),
                            "height": data.get("height"),
                        },
                    )
                )

                # Only cameras with a sub stream report it
                if any(k in data for k in ("BPS2", "bps2")):
                    sensors.append(
                        (
                            "Substream Bitrate",
                            self._bitrate_kbps(data, "BPS2", "bps2"),
                            "mdi:speedometer-medium",
                            rate,
                            {
                                "fps": data.get("FPS2", data.get("fps2")),
                                "width": data.get("width2"),
                                "height": data.get("height2"),
                            },
                        )
                    )

            if self._camera_sensor_allowed(CAMERA_SENSOR_LAST_ALERT, camera):
                sensors.append(
                    (
                        "Last Alert",
                        self.get_last_alert_time(data),
                        "mdi:bell-badge-outline",
                        {ENTITY_SENSOR_DEVICE_CLASS: SensorDeviceClass.TIMESTAMP},
                        {
                            "new_alerts": data.get("newalerts"),
                            "alerts": data.get("nAlerts"),
                            "triggers": data.get("nTriggers"),
                            "clips": data.get("nClips"),
                            "record": data.get("lastalert"),
                        },
                    )
                )

            for label, state, icon, details, attributes in sensors:
                entity = self._config_entity(
                    DOMAIN_SENSOR,
                    f"{base} {label}",
                    camera.id,
                    device_name,
                    CAMERA_SENSOR,
                    state,
                    icon,
                    details,
                )
                entity.attributes.update(attributes)
                self.set_entity(DOMAIN_SENSOR, entity.name, entity)

            for key, (field, label, icon) in CAMERA_STATE_SENSORS.items():
                if not self._camera_sensor_allowed(key, camera):
                    continue

                entity = self._config_entity(
                    DOMAIN_BINARY_SENSOR,
                    f"{base} {label}",
                    camera.id,
                    device_name,
                    CAMERA_SENSOR,
                    bool(data.get(field, False)),
                    icon,
                    {},
                )
                # Plain state, not an alert for the server's Alerts sensor
                entity.event = None
                self.set_entity(DOMAIN_BINARY_SENSOR, entity.name, entity)
        except Exception as ex:
            self.log_exception(ex, f"Failed to generate camera sensors for {camera}")

    def generate_auto_reset_server_switches(self, system_device_name, is_admin):
        try:
            auto_reset = self.ha.auto_reset_manager

            if auto_reset is None or not is_admin:
                return

            for key, label, icon in [
                (AUTO_RESET_KEY_ENABLED, AUTO_RESET_NAME, AUTO_RESET_ICON),
                (
                    AUTO_RESET_KEY_NOTIFICATIONS,
                    AUTO_RESET_NOTIFICATIONS_NAME,
                    AUTO_RESET_NOTIFICATIONS_ICON,
                ),
            ]:
                name = f"{self.integration_title} {label}"
                state = auto_reset.enabled if key == AUTO_RESET_KEY_ENABLED else (
                    auto_reset.notifications
                )
                entity = self._config_entity(
                    DOMAIN_SWITCH,
                    name,
                    None,
                    system_device_name,
                    AUTO_RESET_SERVER_SWITCH,
                    state,
                    icon,
                    {AUTO_RESET_SETTING: key},
                )
                self.set_entity(DOMAIN_SWITCH, name, entity)
        except Exception as ex:
            self.log_exception(ex, "Failed to generate auto reset server switches")

    def generate_camera_auto_reset_entities(self, camera: CameraData, is_admin):
        try:
            auto_reset = self.ha.auto_reset_manager

            # Resetting needs admin rights; only cameras that are watched
            if auto_reset is None or not is_admin:
                return

            if not self.is_problem_sensor_allowed(camera):
                return

            device_name = self.device_manager.get_camera_device_name(camera)
            settings = auto_reset.camera_settings(camera.id)
            base = f"{self.integration_title} {camera.name} {AUTO_RESET_NAME}"

            switch = self._config_entity(
                DOMAIN_SWITCH,
                base,
                camera.id,
                device_name,
                AUTO_RESET_CAMERA_SWITCH,
                settings[AUTO_RESET_KEY_ENABLED],
                AUTO_RESET_ICON,
                {AUTO_RESET_SETTING: AUTO_RESET_KEY_ENABLED},
            )
            self.set_entity(DOMAIN_SWITCH, switch.name, switch)

            for key, label, unit, icon in AUTO_RESET_NUMBERS:
                minimum, maximum, step = AUTO_RESET_LIMITS[key]
                number = self._config_entity(
                    DOMAIN_NUMBER,
                    f"{base} {label}",
                    camera.id,
                    device_name,
                    AUTO_RESET_NUMBER,
                    settings[key],
                    icon,
                    {
                        AUTO_RESET_SETTING: key,
                        ENTITY_NUMBER_MIN: minimum,
                        ENTITY_NUMBER_MAX: maximum,
                        ENTITY_NUMBER_STEP: step,
                        ENTITY_NUMBER_UNIT: unit,
                    },
                )
                self.set_entity(DOMAIN_NUMBER, number.name, number)
        except Exception as ex:
            self.log_exception(ex, f"Failed to generate auto reset entities for {camera}")

    def generate_camera_reset_button(self, camera: CameraData, is_admin: bool):
        try:
            allowed_camera = self.config_data.allowed_camera

            # Reset needs admin rights and a real camera connection
            if not is_admin or not camera.is_physical:
                return

            if allowed_camera is not None and camera.id not in allowed_camera:
                return

            device_name = self.device_manager.get_camera_device_name(camera)
            entity_name = f"{self.integration_title} {camera.name} {BUTTON_RESET_NAME}"

            entity = EntityData()

            entity.id = camera.id
            entity.unique_id = f"{DOMAIN}-{DOMAIN_BUTTON}-{entity_name}"
            entity.name = entity_name
            entity.attributes = {ATTR_FRIENDLY_NAME: entity_name}
            entity.icon = RESET_ICON
            entity.device_name = device_name
            entity.type = BUTTON_RESET_NAME
            entity.details = {ENTITY_BUTTON_DEVICE_CLASS: ButtonDeviceClass.RESTART}

            self.set_entity(DOMAIN_BUTTON, entity.name, entity)
        except Exception as ex:
            self.log_exception(ex, f"Failed to generate reset button for {camera}")

    def generate_server_sensors(self, system_device_name):
        try:
            for entity in [
                self.get_connection_health_sensor(system_device_name),
                self.get_uptime_sensor(system_device_name),
            ]:
                self.set_entity(DOMAIN_SENSOR, entity.name, entity)
        except Exception as ex:
            self.log_exception(ex, "Failed to generate server sensors")

        try:
            for entity in self.get_server_status_sensors(system_device_name):
                self.set_entity(DOMAIN_SENSOR, entity.name, entity)
        except Exception as ex:
            self.log_exception(ex, "Failed to generate server status sensors")

    def _server_sensor(
        self, system_device_name, label, state, icon, details, attributes=None
    ) -> EntityData:
        entity_name = f"{self.integration_title} {label}"

        entity = EntityData()

        entity.unique_id = f"{DOMAIN}-{DOMAIN_SENSOR}-{entity_name}"
        entity.name = entity_name
        entity.state = state
        entity.attributes = {ATTR_FRIENDLY_NAME: entity_name, **(attributes or {})}
        entity.icon = icon
        entity.device_name = system_device_name
        entity.type = label
        entity.details = details

        return entity

    def get_server_status_sensors(self, system_device_name) -> list[EntityData]:
        """CPU, memory, disks, warnings, connections from Blue Iris' status."""
        enabled = self.config_data.server_sensors
        status = self.api.status
        measurement = {ENTITY_SENSOR_STATE_CLASS: SensorStateClass.MEASUREMENT}
        result = []

        if enabled[SERVER_SENSOR_CPU]:
            result.append(
                self._server_sensor(
                    system_device_name,
                    "CPU",
                    parse_number(status.get("cpu")),
                    "mdi:cpu-64-bit",
                    {**measurement, ENTITY_SENSOR_UNIT: PERCENTAGE},
                )
            )

        if enabled[SERVER_SENSOR_MEMORY]:
            result.append(
                self._server_sensor(
                    system_device_name,
                    "Memory",
                    parse_number(status.get("memload")),
                    "mdi:memory",
                    {**measurement, ENTITY_SENSOR_UNIT: PERCENTAGE},
                    {
                        "blue_iris_ram": status.get("mem") or status.get("ram"),
                        "system_ram": status.get("memphys"),
                    },
                )
            )

        if enabled[SERVER_SENSOR_WARNINGS]:
            result.append(
                self._server_sensor(
                    system_device_name,
                    "Warnings",
                    parse_number(status.get("warnings")),
                    "mdi:alert-outline",
                    measurement,
                )
            )

        if enabled[SERVER_SENSOR_CONNECTIONS]:
            result.append(
                self._server_sensor(
                    system_device_name,
                    "Connections",
                    parse_number(status.get("cxns")),
                    "mdi:lan-connect",
                    {**measurement, ENTITY_SENSOR_CATEGORY: EntityCategory.DIAGNOSTIC},
                )
            )

        discs = status.get("discs")
        if enabled[SERVER_SENSOR_DISKS] and isinstance(discs, list):
            for disc in discs:
                if not isinstance(disc, dict):
                    continue

                raw_name = next(
                    (disc[k] for k in ("disc", "disk", "name", "drive") if disc.get(k)),
                    None,
                )
                if raw_name is None:
                    continue

                name = str(raw_name).strip().rstrip(":\\")
                free = parse_size_gb(disc.get("free"))
                total = parse_size_gb(disc.get("total"))

                attributes = {
                    "drive": name,
                    # As sent by Blue Iris, to check the conversion
                    "allocated": disc.get("allocated"),
                    "used": disc.get("used"),
                    "free_raw": disc.get("free"),
                    "total": disc.get("total"),
                    "free_percent": None
                    if free is None or not total
                    else round(free / total * 100, 1),
                }

                result.append(
                    self._server_sensor(
                        system_device_name,
                        f"Disk {name} Free",
                        free,
                        "mdi:harddisk",
                        {
                            **measurement,
                            ENTITY_SENSOR_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
                            ENTITY_SENSOR_UNIT: UnitOfInformation.GIBIBYTES,
                        },
                        attributes,
                    )
                )

        return result

    def get_main_binary_sensor(self) -> EntityData:
        entity = None

        try:
            entity_name = f"{self.integration_title} Alerts"

            unique_id = f"{DOMAIN}-{DOMAIN_BINARY_SENSOR}-MAIN-{entity_name}"

            binary_sensors = self.get_entities(DOMAIN_BINARY_SENSOR)

            alerts = {}
            for binary_sensor_name in binary_sensors:
                entity = binary_sensors[binary_sensor_name]
                entity_event = entity.event
                entity_state = entity.state

                # Only event sensors (MQTT, Problem); not plain state sensors
                # nor this Alerts sensor itself, which kept itself on
                if entity_event:
                    event_alerts = alerts.get(entity_event, [])
                    is_on = entity_state

                    if entity_event == SENSOR_CONNECTIVITY_NAME:
                        is_on = not is_on

                    if is_on:
                        event_alerts.append(binary_sensor_name)

                        alerts[entity_event] = event_alerts

            state = len(alerts.keys()) > 0

            attributes = {ATTR_FRIENDLY_NAME: entity_name}

            for alert_name in alerts:
                current_alerts = alerts[alert_name]
                attributes[alert_name] = ", ".join(current_alerts)

            entity = EntityData()

            entity.unique_id = unique_id
            entity.name = entity_name
            entity.state = state
            entity.attributes = attributes
            entity.icon = DEFAULT_ICON
            entity.device_name = self.system_device_name
            entity.type = SENSOR_MAIN_NAME
            entity.binary_sensor_device_class = BinarySensorDeviceClass.PROBLEM
        except Exception as ex:
            self.log_exception(ex, "Failed to get main binary sensor")

        return entity

    def generate_main_binary_sensor(self):
        try:
            entity = self.get_main_binary_sensor()
            entity_name = entity.name

            self.set_entity(DOMAIN_BINARY_SENSOR, entity_name, entity)
        except Exception as ex:
            self.log_exception(ex, "Failed to generate main binary sensor")

    def get_camera_entity(
        self, camera: CameraData, sensor_type_name, camera_device_name
    ) -> EntityData:
        entity = None

        try:
            entity_name = f"{self.integration_title} {camera.name} {sensor_type_name}"
            unique_id = f"{DOMAIN}-{DOMAIN_BINARY_SENSOR}-{entity_name}"

            state_topic = MQTT_ALL_TOPIC.replace("+", camera.id)

            default_state = sensor_type_name in NEGATIVE_SENSOR_STATE

            state = self.get_mqtt_state(state_topic, sensor_type_name, default_state)

            device_class = CAMERA_SENSORS.get(sensor_type_name)

            attributes = {ATTR_FRIENDLY_NAME: entity_name}

            entity = EntityData()

            entity.id = camera.id
            entity.unique_id = unique_id
            entity.name = entity_name
            entity.state = state
            entity.attributes = attributes
            entity.icon = DEFAULT_ICON
            entity.device_name = camera_device_name
            entity.topic = state_topic
            entity.event = sensor_type_name
            entity.binary_sensor_device_class = device_class
            entity.type = sensor_type_name
        except Exception as ex:
            self.log_exception(
                ex, f"Failed to get camera motion binary sensor for {camera}"
            )

        return entity

    def generate_camera_binary_sensors(self, camera: CameraData):
        entities = []

        try:
            camera_device_name = self.device_manager.get_camera_device_name(camera)
            for sensor_type_name in CAMERA_SENSORS.keys():
                if self.config_manager.is_allowed_sensor(camera, sensor_type_name):
                    entity = self.get_camera_entity(
                        camera, sensor_type_name, camera_device_name
                    )
                    entities.append(entity)

            for entity in entities:
                entity_name = entity.name
                state = entity.state
                topic = entity.topic
                event_type = entity.event

                self.set_mqtt_state(topic, event_type, state)

                self.set_entity(DOMAIN_BINARY_SENSOR, entity_name, entity)

        except Exception as ex:
            self.log_exception(ex, f"Failed to generate binary sensors for {camera}")

        return entities

    def get_camera_component(self, camera: CameraData) -> EntityData:
        entity = None
        try:
            device_name = self.device_manager.get_camera_device_name(camera)

            entity_name = f"{self.integration_title} {camera.name}"
            username = self.config_data.username
            password = self.config_data.password_clear_text
            base_url = self.api.base_url
            session_id = self.api.session_id

            unique_id = f"{DOMAIN}-{DOMAIN_CAMERA}-{entity_name}"

            still_image_url = f"{base_url}/image/{camera.id}?session={session_id}"
            still_image_url_template = cv.template(still_image_url)

            stream_config = STREAM_VIDEO.get(self.config_data.stream_type, {})

            file_name = stream_config.get("file_name", "")
            stream_name = stream_config.get("stream_name")

            support_stream = False

            if DOMAIN_STREAM in self.hass.data:
                support_stream = self.config_data.support_stream

            stream_source = (
                f"{base_url}/{stream_name}/{camera.id}/{file_name}?session={session_id}"
            )

            fps = camera.data.get("FPS", 1)

            if fps < 1:
                fps = 1

            camera_details = {
                CONF_NAME: f"{entity_name}",
                CONF_STILL_IMAGE_URL: still_image_url_template,
                CONF_STREAM_SOURCE: stream_source,
                CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
                CONF_FRAMERATE: fps,
                CONF_CONTENT_TYPE: DEFAULT_CONTENT_TYPE,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_AUTHENTICATION: AUTHENTICATION_BASIC,
                CONF_SUPPORT_STREAM: support_stream,
            }

            attributes = {
                ATTR_FRIENDLY_NAME: entity_name,
                CONF_STREAM_SOURCE: stream_source,
                CONF_STILL_IMAGE_URL: still_image_url,
            }

            for key in ATTR_BLUE_IRIS_CAMERA:
                key_name = ATTR_BLUE_IRIS_CAMERA[key]
                attributes[key_name] = camera.data.get(key, NOT_AVAILABLE)

            entity = EntityData()

            entity.id = camera.id
            entity.unique_id = unique_id
            entity.name = entity_name
            entity.attributes = attributes
            entity.icon = DEFAULT_ICON
            entity.device_name = device_name
            entity.details = camera_details
            entity.state = camera.is_online

        except Exception as ex:
            self.log_exception(ex, f"Failed to get camera for {camera}")

        return entity

    def generate_camera_component(self, camera: CameraData):
        try:
            entity = self.get_camera_component(camera)

            if entity is not None:
                camera_id = entity.id
                allowed_camera = self.config_data.allowed_camera

                if allowed_camera is None or camera_id in allowed_camera:
                    entity_name = entity.name
                    self.set_entity(DOMAIN_CAMERA, entity_name, entity)

        except Exception as ex:
            self.log_exception(ex, f"Failed to generate camera for {camera}")

    @staticmethod
    def log_exception(ex, message):
        exc_type, exc_obj, tb = sys.exc_info()
        line_number = tb.tb_lineno

        _LOGGER.error(f"{message}, Error: {str(ex)}, Line: {line_number}")
