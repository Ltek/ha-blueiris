import logging
from typing import Any, Optional

from cryptography.fernet import InvalidToken
from voluptuous import Marker

from homeassistant.components.mqtt import DATA_MQTT
from homeassistant.components.stream.const import DOMAIN as DOMAIN_STREAM
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .. import get_ha
from ..api.blue_iris_api import BlueIrisApi
from ..helpers.const import *
from ..managers.configuration_manager import ConfigManager
from ..managers.password_manager import PasswordManager
from ..models import LoginError
from ..models.camera_data import CameraData
from ..models.config_data import ConfigData
from .storage_manager import StorageManager

_LOGGER = logging.getLogger(__name__)


class ConfigFlowManager:
    _config_manager: ConfigManager
    _password_manager: PasswordManager
    _options: Optional[dict]
    _data: Optional[dict]
    _config_entry: Optional[ConfigEntry]
    api: Optional[BlueIrisApi]
    title: str

    def __init__(self):
        self._config_entry = None

        self._options = None
        self._data = None

        self._is_initialized = True
        self._hass = None
        self.api = None
        self.title = DEFAULT_NAME

        self._available_actions = [CONF_GENERATE_CONFIG_FILES]

    async def initialize(self, hass, config_entry: Optional[ConfigEntry] = None):
        self._config_entry = config_entry
        self._hass = hass

        self._password_manager = PasswordManager(self._hass)
        self._config_manager = ConfigManager(self._password_manager)

        data = {}
        options = {}

        if self._config_entry is not None:
            data = self._config_entry.data
            options = self._config_entry.options

            self.title = self._config_entry.title

        await self.update_data(data, CONFIG_FLOW_INIT)
        await self.update_options(options, CONFIG_FLOW_INIT)

    @property
    def config_data(self) -> ConfigData:
        return self._config_manager.data

    async def update_options(self, options: dict, flow: str):
        _LOGGER.debug("Update options")
        validate_login = False

        new_options = await self._clone_items(options, flow)

        if flow == CONFIG_FLOW_OPTIONS:
            validate_login = self._should_validate_login(new_options)

            self._move_option_to_data(new_options)

            await self._set_actions(new_options)

        self._options = new_options

        await self._update_entry()

        if validate_login:
            await self._handle_data(flow)

        return new_options

    async def update_data(self, data: dict, flow: str):
        _LOGGER.debug("Update data")

        self._data = await self._clone_items(data, flow)

        await self._update_entry()

        await self._handle_data(flow)

        return self._data

    def _get_default_fields(
        self, _flow, config_data: Optional[ConfigData] = None
    ) -> dict[Marker, Any]:
        if config_data is None:
            config_data = self.config_data

        fields = {
            vol.Optional(CONF_HOST, default=config_data.host): str,
            vol.Optional(CONF_PORT, default=config_data.port): str,
            vol.Optional(CONF_SSL, default=config_data.ssl): bool,
            vol.Optional(CONF_USERNAME, default=config_data.username): str,
            vol.Optional(CONF_PASSWORD, default=config_data.password_clear_text): str,
        }

        return fields

    async def get_default_data(self, user_input) -> vol.Schema:
        config_data = await self._config_manager.get_basic_data(user_input)

        fields = self._get_default_fields(CONFIG_FLOW_DATA, config_data)

        data_schema = vol.Schema(fields)

        return data_schema

    def get_option_categories(self) -> list[dict]:
        """Selectable component categories that apply to this server.

        checked is the saved option: None means all (also cameras added to
        Blue Iris later), a list means only those items.
        """
        config_data = self.config_data
        ha = self._get_ha(self._config_entry.entry_id)

        camera_list: list[CameraData] = ha.api.camera_list

        is_admin = ha.api.data.get("admin", False)
        has_mqtt = DATA_MQTT in self._hass.data

        profiles_list = ha.api.data.get("profiles", [])
        schedules_list = ha.api.data.get("schedules", [])
        supported_camera = self._get_camera_options(camera_list)
        supported_audio_sensor = self._get_camera_options(camera_list, CAMERA_HAS_AUDIO)
        supported_camera_sensor = self._get_camera_options(
            camera_list, CAMERA_IS_SYSTEM
        )

        supported_physical_camera = self._get_camera_options(
            camera_list, CAMERA_IS_PHYSICAL
        )

        supported_profile = self._get_profile_options(profiles_list)
        supported_schedule = self._get_schedule_options(schedules_list)

        categories = [
            (CONF_ALLOWED_CAMERA, config_data.allowed_camera, supported_camera, True),
            (
                CONF_ALLOWED_PROBLEM_SENSOR,
                config_data.allowed_problem_sensor,
                supported_physical_camera,
                True,
            ),
            (
                CONF_ALLOWED_MOTION_SENSOR,
                config_data.allowed_motion_sensor,
                supported_camera_sensor,
                has_mqtt,
            ),
            (
                CONF_ALLOWED_CONNECTIVITY_SENSOR,
                config_data.allowed_connectivity_sensor,
                supported_camera_sensor,
                has_mqtt,
            ),
            (
                CONF_ALLOWED_AUDIO_SENSOR,
                config_data.allowed_audio_sensor,
                supported_audio_sensor,
                has_mqtt,
            ),
            (
                CONF_ALLOWED_DIO_SENSOR,
                config_data.allowed_dio_sensor,
                supported_camera_sensor,
                has_mqtt,
            ),
            (
                CONF_ALLOWED_EXTERNAL_SENSOR,
                config_data.allowed_external_sensor,
                supported_camera_sensor,
                has_mqtt,
            ),
            (CONF_ALLOWED_PROFILE, config_data.allowed_profile, supported_profile, is_admin),
            (
                CONF_ALLOWED_SCHEDULE,
                config_data.allowed_schedule,
                supported_schedule,
                is_admin,
            ),
        ]

        for key, option_key in CONF_CAMERA_CONTROLS.items():
            categories.append(
                (
                    option_key,
                    config_data.camera_controls[key],
                    supported_physical_camera,
                    is_admin,
                )
            )

        for key, option_key in CONF_CAMERA_SENSORS.items():
            categories.append(
                (
                    option_key,
                    config_data.camera_sensors[key],
                    supported_physical_camera,
                    True,
                )
            )

        result = []
        for name, checked, items, enabled in categories:
            if checked is not None:
                checked = [i for i in checked if i in items]

            result.append(
                {
                    "name": name,
                    "items": items,
                    "checked": checked,
                    "enabled": enabled,
                }
            )

        return result

    @staticmethod
    def _category_mode(category: dict) -> str:
        checked = category["checked"]

        if checked is None:
            return OPTION_MODE_ALL

        if len(checked) == 0:
            return OPTION_MODE_NONE

        return OPTION_MODE_CUSTOM

    def get_options_main_schema(self, categories: list[dict]) -> vol.Schema:
        """Page 1: All / None / Choose per category, plus the other settings."""
        config_data = self.config_data

        fields = {}
        section_fields: dict[str, dict] = {}

        for category in categories:
            if not category["enabled"]:
                continue

            total = len(category["items"])
            checked = category["checked"]
            selected = total if checked is None else len(checked)

            mode_options = [
                SelectOptionDict(value=OPTION_MODE_ALL, label=f"All ({total})"),
                SelectOptionDict(value=OPTION_MODE_NONE, label="None (0)"),
                SelectOptionDict(
                    value=OPTION_MODE_CUSTOM,
                    label=f"Choose… ({selected} of {total} selected)",
                ),
            ]

            section_name = CATEGORY_SECTIONS[category["name"]]
            section_fields.setdefault(section_name, {})[
                vol.Required(category["name"], default=self._category_mode(category))
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=mode_options, mode=SelectSelectorMode.DROPDOWN
                )
            )

        # Empty sections (no MQTT, not admin) are left out
        for section_name, collapsed in SECTION_COLLAPSED.items():
            if section_name in section_fields:
                fields[vol.Required(section_name)] = section(
                    vol.Schema(section_fields[section_name]), {"collapsed": collapsed}
                )

        fields[vol.Required(OPTION_SECTION_SERVER)] = section(
            vol.Schema(self.get_server_fields(config_data)), {"collapsed": True}
        )

        connection_fields = self._get_default_fields(CONFIG_FLOW_OPTIONS)
        connection_fields[vol.Optional(CONF_CLEAR_CREDENTIALS, default=False)] = bool

        fields[vol.Required(OPTION_SECTION_CONNECTION)] = section(
            vol.Schema(connection_fields), {"collapsed": True}
        )

        general_fields = {
            vol.Optional(CONF_STREAM_TYPE, default=config_data.stream_type): vol.In(
                list(STREAM_VIDEO.keys())
            ),
        }

        if DOMAIN_STREAM in self._hass.data:
            general_fields[
                vol.Optional(CONF_SUPPORT_STREAM, default=config_data.support_stream)
            ] = bool

        general_fields[
            vol.Optional(CONF_LOG_LEVEL, default=config_data.log_level)
        ] = SelectSelector(
            SelectSelectorConfig(options=LOG_LEVELS, mode=SelectSelectorMode.DROPDOWN)
        )
        general_fields[vol.Optional(CONF_GENERATE_CONFIG_FILES, default=False)] = bool

        fields[vol.Required(OPTION_SECTION_GENERAL)] = section(
            vol.Schema(general_fields), {"collapsed": True}
        )

        # Auto reset needs admin rights, like the reset itself
        ha = self._get_ha(self._config_entry.entry_id)
        if ha.api.data.get("admin", False):
            fields[vol.Required(OPTION_SECTION_AUTO_RESET)] = section(
                vol.Schema(
                    self._get_auto_reset_fields(
                        config_data, ha.auto_reset_manager.notifications
                    )
                ),
                {"collapsed": True},
            )

        return vol.Schema(fields)

    @staticmethod
    def get_server_fields(config_data: ConfigData) -> dict:
        return {
            vol.Optional(option_key, default=config_data.server_sensors[key]): (
                BooleanSelector()
            )
            for key, option_key in CONF_SERVER_SENSORS.items()
        }

    def get_setup_features_schema(self) -> vol.Schema:
        """Setup's second page: features that need no camera list."""
        config_data = self.config_data
        fields = {
            vol.Required(OPTION_SECTION_SERVER): section(
                vol.Schema(self.get_server_fields(config_data)), {"collapsed": False}
            )
        }

        if self.api is not None and self.api.data.get("admin", False):
            auto_reset_fields = {
                key: value
                for key, value in self._get_auto_reset_fields(config_data, True).items()
                if str(key)
                not in (CONF_AUTO_RESET_NOTIFICATIONS, CONF_AUTO_RESET_APPLY_DEFAULTS)
            }
            fields[vol.Required(OPTION_SECTION_AUTO_RESET)] = section(
                vol.Schema(auto_reset_fields), {"collapsed": False}
            )

        return vol.Schema(fields)

    @staticmethod
    def setup_features_options(features_input: dict) -> dict:
        options = ConfigFlowManager.flatten_sections(features_input)

        for key in (AUTO_RESET_KEY_ATTEMPTS, AUTO_RESET_KEY_INTERVAL):
            option_key = CONF_AUTO_RESET_DEFAULTS[key]
            if isinstance(options.get(option_key), float):
                options[option_key] = int(round(options[option_key]))

        return options

    @staticmethod
    def flatten_sections(main_input: dict) -> dict:
        """Page 1 values without their section nesting."""
        flat = {}

        for key, value in main_input.items():
            if isinstance(value, dict):
                flat.update(value)
            else:
                flat[key] = value

        return flat

    @staticmethod
    def _get_auto_reset_fields(config_data: ConfigData, notifications: bool) -> dict:
        defaults = config_data.auto_reset_defaults
        fields = {
            vol.Optional(
                CONF_AUTO_RESET_NOTIFICATIONS, default=notifications
            ): BooleanSelector(),
            vol.Optional(
                CONF_AUTO_RESET_DEFAULTS[AUTO_RESET_KEY_ENABLED],
                default=defaults[AUTO_RESET_KEY_ENABLED],
            ): BooleanSelector(),
        }

        for key, _label, unit, _icon in AUTO_RESET_NUMBERS:
            minimum, maximum, step = AUTO_RESET_LIMITS[key]
            fields[
                vol.Optional(CONF_AUTO_RESET_DEFAULTS[key], default=defaults[key])
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=minimum,
                    max=maximum,
                    step=step,
                    mode=NumberSelectorMode.BOX,
                    **({} if unit is None else {"unit_of_measurement": unit}),
                )
            )

        fields[
            vol.Optional(CONF_AUTO_RESET_APPLY_DEFAULTS, default=False)
        ] = BooleanSelector()

        return fields

    @staticmethod
    def get_options_items_schema(
        categories: list[dict], custom_names: list[str]
    ) -> vol.Schema:
        """Page 2: a checkbox list for each category set to Choose."""
        fields = {}

        for category in categories:
            name = category["name"]

            if name not in custom_names:
                continue

            items = category["items"]
            checked = category["checked"]
            default = list(items.keys()) if checked is None else checked

            options = [
                SelectOptionDict(value=key, label=label) for key, label in items.items()
            ]

            fields[vol.Required(name)] = section(
                vol.Schema(
                    {
                        vol.Optional(OPTION_ITEMS, default=default): SelectSelector(
                            SelectSelectorConfig(
                                options=options,
                                multiple=True,
                                mode=SelectSelectorMode.LIST,
                            )
                        )
                    }
                ),
                {"collapsed": False},
            )

        return vol.Schema(fields)

    @staticmethod
    def build_options_input(
        categories: list[dict], main_input: dict, items_input: Optional[dict]
    ) -> dict:
        """Merge both pages into the flat options update_options expects.

        All -> option left out (no limit), None -> [], Choose -> the ticked
        items. Categories hidden on page 1 (no MQTT / not admin) keep their
        saved value.
        """
        flat = ConfigFlowManager.flatten_sections(main_input)
        category_names = {category["name"] for category in categories}

        # Everything except the category modes is a setting as entered
        result = {k: v for k, v in flat.items() if k not in category_names}

        # Number selectors return floats; keep whole numbers as int
        for key in (AUTO_RESET_KEY_ATTEMPTS, AUTO_RESET_KEY_INTERVAL):
            option_key = CONF_AUTO_RESET_DEFAULTS[key]
            if isinstance(result.get(option_key), float):
                result[option_key] = int(round(result[option_key]))

        items_input = items_input or {}

        for category in categories:
            name = category["name"]

            if not category["enabled"]:
                if category["checked"] is not None or name in DEFAULT_OFF_OPTION_KEYS:
                    result[name] = category["checked"]
                continue

            mode = flat.get(name, OPTION_MODE_ALL)

            if mode == OPTION_MODE_ALL and name in DEFAULT_OFF_OPTION_KEYS:
                # Leaving it out would mean the default, which is None
                result[name] = None

            elif mode == OPTION_MODE_NONE:
                result[name] = []

            elif mode == OPTION_MODE_CUSTOM:
                result[name] = list(items_input.get(name, {}).get(OPTION_ITEMS, []))

        return result

    async def _update_entry(self):
        try:
            entry = ConfigEntry(
                unique_id="",
                version=0,
                minor_version=0,
                domain="",
                title="",
                data=self._data,
                source="",
                options=self._options,
                discovery_keys={},
                subentries_data={},
            )

            await self._config_manager.update(entry)
        except InvalidToken:
            _LOGGER.debug("Reset password")

            del self._data[CONF_PASSWORD]

            entry = ConfigEntry(
                unique_id="",
                version=0,
                minor_version=0,
                domain="",
                title="",
                data=self._data,
                source="",
                options=self._options,
                discovery_keys={},
                subentries_data={},
            )

            await self._config_manager.update(entry)

    async def clear_credentials(self, user_input):
        user_input[CONF_CLEAR_CREDENTIALS] = True

        await self._handle_password(user_input)

    async def _handle_password(self, user_input):
        if CONF_CLEAR_CREDENTIALS in user_input:
            clear_credentials = user_input.get(CONF_CLEAR_CREDENTIALS)

            if clear_credentials:
                del user_input[CONF_USERNAME]
                del user_input[CONF_PASSWORD]

            del user_input[CONF_CLEAR_CREDENTIALS]

        if CONF_PASSWORD in user_input:
            password_clear_text = user_input[CONF_PASSWORD]
            password = await self._password_manager.encrypt(password_clear_text)

            user_input[CONF_PASSWORD] = password

    async def _clone_items(self, user_input, flow: str):
        new_user_input = {}

        if user_input is not None:
            for key in user_input:
                user_input_data = user_input[key]

                new_user_input[key] = user_input_data

            if flow != CONFIG_FLOW_INIT:
                await self._handle_password(new_user_input)

        return new_user_input

    @staticmethod
    def clone_items(user_input):
        new_user_input = {}

        if user_input is not None:
            for key in user_input:
                user_input_data = user_input[key]

                new_user_input[key] = user_input_data

        return new_user_input

    def _should_validate_login(self, user_input: dict):
        validate_login = False
        data = self._data

        for conf in CONF_ARR:
            if data.get(conf) != user_input.get(conf):
                validate_login = True

                break

        return validate_login

    async def _set_actions(self, options):
        actions = []

        for action in self._available_actions:
            _LOGGER.debug(f"Looking for {action}")

            if action in options:
                action_enabled = options.get(action, False)

                _LOGGER.debug(f"Action: {action}, set to {action_enabled}")

                if action_enabled:
                    actions.append(action)

                del options[action]

        generate_configuration_files = CONF_GENERATE_CONFIG_FILES in actions

        storage_manager = StorageManager(self._hass)
        data = await storage_manager.async_load_from_store()
        integration_data = data.integrations.get(self.title, {})
        integration_data[CONF_GENERATE_CONFIG_FILES] = generate_configuration_files

        await storage_manager.async_save_to_store(data)

    def _get_ha(self, key: str = None):
        if key is None:
            key = self.title

        ha = get_ha(self._hass, key)

        return ha

    def _move_option_to_data(self, options):
        for conf in CONF_ARR:
            if conf in options:
                self._data[conf] = options[conf]

                del options[conf]

    async def _handle_data(self, flow):
        if flow != CONFIG_FLOW_INIT:
            await self._valid_login()

        if flow == CONFIG_FLOW_OPTIONS:
            config_entries = self._hass.config_entries
            config_entries.async_update_entry(self._config_entry, data=self._data)

    @staticmethod
    def _get_camera_options(
        camera_list: list[CameraData], include: Optional[str] = None
    ):
        available_items = {}

        for camera in camera_list:
            if include == CAMERA_IS_SYSTEM:
                skip = camera.is_system
            elif include == CAMERA_HAS_AUDIO:
                skip = not camera.has_audio or camera.is_system
            elif include == CAMERA_IS_PHYSICAL:
                skip = not camera.is_physical
            else:
                skip = False

            if not skip:
                available_items[camera.id] = camera.name

        return available_items

    @staticmethod
    def _get_profile_options(profiles_list):
        available_items = {}

        for profile_name in profiles_list:
            profile_id = profiles_list.index(profile_name)

            available_items[str(profile_id)] = profile_name

        return available_items

    @staticmethod
    def _get_schedule_options(schedules_list):
        available_items = {}

        for schedule_name in schedules_list:
            schedule_id = schedules_list.index(schedule_name)

            available_items[str(schedule_id)] = schedule_name

        return available_items

    async def _valid_login(self):
        errors = None

        config_data = self._config_manager.data

        api = BlueIrisApi(self._hass, self._config_manager)
        await api.initialize()

        if not api.is_logged_in:
            _LOGGER.warning(f"Failed to access BlueIris Server ({config_data.host})")
            errors = {"base": "invalid_server_details"}
        else:
            has_credentials = config_data.has_credentials

            if has_credentials and not api.data.get("admin", False):
                _LOGGER.warning(
                    f"Failed to login BlueIris ({config_data.host}) due to invalid credentials"
                )
                errors = {"base": "invalid_admin_credentials"}

            # Kept for the setup flow's features page (admin-only settings)
            self.api = api

            system_name = api.data.get("system name")
            if system_name is not None:
                if system_name.strip():
                    self.title = system_name

        if errors is not None:
            raise LoginError(errors)
