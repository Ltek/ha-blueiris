"""Config flow to configure BlueIris."""
import logging

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .helpers.const import *
from .managers.config_flow_manager import ConfigFlowManager
from .models import AlreadyExistsError, LoginError

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class DomainFlowHandler(config_entries.ConfigFlow):
    """Handle a domain config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        super().__init__()

        self._config_flow = ConfigFlowManager()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DomainOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.debug(f"Starting async_step_user of {DEFAULT_NAME}")

        errors = None

        await self._config_flow.initialize(self.hass)

        new_user_input = self._config_flow.clone_items(user_input)

        if user_input is not None:
            try:
                data = await self._config_flow.update_data(user_input, CONFIG_FLOW_DATA)

                return self.async_create_entry(title=self._config_flow.title, data=data)
            except LoginError as lex:
                await self._config_flow.clear_credentials(new_user_input)

                _LOGGER.warning("Cannot complete login")

                errors = lex.errors

            except AlreadyExistsError as aeex:
                _LOGGER.warning(
                    f"{DEFAULT_NAME} with {ENTRY_PRIMARY_KEY}: {aeex.title} already exists"
                )

                errors = {"base": "already_configured"}

        schema = await self._config_flow.get_default_data(new_user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=new_user_input,
        )

    async def async_step_import(self, info):
        """Import existing configuration."""
        _LOGGER.debug(f"Starting async_step_import of {DEFAULT_NAME}")

        title = f"{DEFAULT_NAME} (import from configuration.yaml)"

        return self.async_create_entry(title=title, data=info)


class DomainOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle domain options.

    Page 1 (blue_iris_additional_settings): All / None / Choose per
    component category, plus connection and general settings.
    Page 2 (select_items): checkbox lists for the categories set to Choose.
    """

    def __init__(self, config_entry: ConfigEntry):
        """Initialize domain options flow."""
        super().__init__()

        self._config_entry = config_entry

        self._config_flow = ConfigFlowManager()
        self._categories = None
        self._main_input = None

    async def async_step_init(self, user_input=None):
        """Manage the domain options."""
        return await self.async_step_blue_iris_additional_settings(user_input)

    async def _async_load(self):
        if self._categories is None:
            await self._config_flow.initialize(self.hass, self._config_entry)
            self._categories = self._config_flow.get_option_categories()

    def _custom_categories(self) -> list[str]:
        return [
            category["name"]
            for category in self._categories
            if category["enabled"]
            and self._main_input.get(category["name"]) == OPTION_MODE_CUSTOM
        ]

    async def async_step_blue_iris_additional_settings(
        self, user_input=None, errors=None
    ):
        _LOGGER.debug(f"Starting additional settings step: {user_input}")

        await self._async_load()

        if user_input is not None:
            self._main_input = user_input

            if self._custom_categories():
                return await self.async_step_select_items()

            return await self._async_save(None)

        schema = self._config_flow.get_options_main_schema(self._categories)

        if self._main_input is not None:
            # Coming back after a failed save: keep what was entered
            schema = self.add_suggested_values_to_schema(schema, self._main_input)

        return self.async_show_form(
            step_id="blue_iris_additional_settings",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_items(self, user_input=None):
        await self._async_load()

        if user_input is not None:
            return await self._async_save(user_input)

        schema = self._config_flow.get_options_items_schema(
            self._categories, self._custom_categories()
        )

        return self.async_show_form(step_id="select_items", data_schema=schema)

    async def _async_save(self, items_input):
        # Start from the saved entry each time, so a retry after a failed
        # login is validated again
        await self._config_flow.initialize(self.hass, self._config_entry)

        options_input = self._config_flow.build_options_input(
            self._categories, self._main_input, items_input
        )

        try:
            options = await self._config_flow.update_options(
                options_input, CONFIG_FLOW_OPTIONS
            )

            return self.async_create_entry(title=self._config_flow.title, data=options)

        except LoginError as lex:
            _LOGGER.warning("Cannot complete login")
            errors = lex.errors

        except AlreadyExistsError as aeex:
            _LOGGER.warning(
                f"{DEFAULT_NAME} with {ENTRY_PRIMARY_KEY}: {aeex.title} already exists"
            )

            errors = {"base": "already_configured"}

        # Don't re-show a password that just failed
        connection = dict(self._main_input.get(OPTION_SECTION_CONNECTION, {}))
        connection.pop(CONF_PASSWORD, None)
        self._main_input = {**self._main_input, OPTION_SECTION_CONNECTION: connection}

        return await self.async_step_blue_iris_additional_settings(errors=errors)
