from datetime import datetime, timezone
import hashlib
import json
import logging
import sys
import asyncio
from typing import Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from ..helpers.const import (
    CONNECTION_STATE_AUTH_FAILED,
    CONNECTION_STATE_CONNECTED,
    CONNECTION_STATE_CONNECTING,
    CONNECTION_STATE_ERROR,
    CONNECTION_STATE_UNREACHABLE,
)
from ..managers.configuration_manager import ConfigManager
from ..models.camera_data import CameraData

REQUIREMENTS = ["aiohttp"]

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = ClientTimeout(total=10)
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class BlueIrisCommandError(Exception):
    """A Blue Iris command could not be completed."""


class BlueIrisApi:
    """Handles Blue Iris data retrieval and control."""

    is_logged_in: bool
    session_id: Optional[str]
    session: Optional[ClientSession]
    data: dict
    status: dict
    camera_list: list[CameraData]
    hass: HomeAssistant
    config_manager: ConfigManager
    base_url: str
    url: str

    def __init__(self, hass: HomeAssistant, config_manager: ConfigManager):
        try:
            self._last_update = datetime.now()
            self.hass = hass
            self.config_manager = config_manager
            self.session_id = None
            self.session = None

            # Connection health, refreshed by every async_update
            self.last_post_reachable = None
            self.last_update_success = None
            self.last_success_time = None
            self.consecutive_failures = 0
            self.connection_state = CONNECTION_STATE_CONNECTING
        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            _LOGGER.error(f"Failed to load BlueIris API, error: {ex}, line: {tb.tb_lineno}")

    @property
    def is_initialized(self):
        return self.session is not None and not self.session.closed

    @property
    def config_data(self):
        return self.config_manager.data

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            if self.hass is None:
                self.session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
            else:
                self.session = async_create_clientsession(hass=self.hass, timeout=DEFAULT_TIMEOUT)

    async def async_close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def async_post(self, data):
        await self.ensure_session()
        result = None

        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.post(self.url, data=json.dumps(data), ssl=False) as response:
                    _LOGGER.debug(f"Status of {self.url}: {response.status}")
                    response.raise_for_status()
                    result = await response.json()
                    self.last_post_reachable = True
                    _LOGGER.debug(f"Full result of {data}: {result}")
                    self._last_update = datetime.now()
                    return result
            except aiohttp.ClientError as ex:
                _LOGGER.warning(f"Attempt {attempt+1} failed: {ex}")
                await asyncio.sleep(RETRY_DELAY)
            except Exception as ex:
                exc_type, exc_obj, tb = sys.exc_info()
                _LOGGER.error(f"Unexpected error on attempt {attempt+1}, Error: {ex}, Line: {tb.tb_lineno}")
                await asyncio.sleep(RETRY_DELAY)

        _LOGGER.error(f"All attempts to POST to {self.url} failed.")
        self.last_post_reachable = False
        return None

    async def async_verified_post(self, data):
        for i in range(2):
            result = await self.async_post(data)
            if result is not None and result.get("result") != "fail":
                return result

            _LOGGER.warning(f"Request #{i} to BlueIris ({self.base_url}) failed, Data: {data}, Response: {result}")
            await self.login()

        return None

    async def initialize(self):
        _LOGGER.debug("Initializing BlueIris")
        try:
            config_data = self.config_data
            self.base_url = f"{config_data.protocol}://{config_data.host}:{config_data.port}"
            self.url = f"{self.base_url}/json"

            self.is_logged_in = False
            self.data = {}
            self.status = {}
            self.camera_list = []

            await self.ensure_session()
            await self.login()
        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            _LOGGER.error(f"Failed to initialize BlueIris API ({self.base_url}), error: {ex}, line: {tb.tb_lineno}")

    async def async_update(self):
        _LOGGER.debug(f"Updating data from BI Server ({self.config_manager.config_entry.title})")
        camera_loaded = await self.load_camera()
        status_loaded = await self.load_status()

        self._update_connection_health(camera_loaded and status_loaded)

    def _update_connection_health(self, success: bool):
        previous_state = self.connection_state

        self.last_update_success = success

        if success:
            self.consecutive_failures = 0
            self.last_success_time = datetime.now(timezone.utc)
            self.connection_state = CONNECTION_STATE_CONNECTED

        else:
            self.consecutive_failures += 1

            if self.last_post_reachable is False:
                self.connection_state = CONNECTION_STATE_UNREACHABLE
            elif not self.is_logged_in:
                self.connection_state = CONNECTION_STATE_AUTH_FAILED
            else:
                self.connection_state = CONNECTION_STATE_ERROR

        if self.connection_state != previous_state:
            _LOGGER.debug(
                f"Connection state changed from {previous_state} to {self.connection_state}, "
                f"consecutive failures: {self.consecutive_failures}"
            )

    async def load_session_id(self):
        _LOGGER.debug("Retrieving session ID")
        response = await self.async_post({"cmd": "login"})
        self.session_id = response.get("session") if response else None
        self.is_logged_in = False

    async def login(self):
        _LOGGER.debug("Performing login")
        try:
            await self.load_session_id()
            if self.session_id:
                config_data = self.config_manager.data
                token_request = f"{config_data.username}:{self.session_id}:{config_data.password_clear_text}"
                token = hashlib.md5(token_request.encode("utf-8")).hexdigest()

                result = await self.async_post({
                    "cmd": "login",
                    "session": self.session_id,
                    "response": token,
                })

                if result and result.get("result") == "success":
                    self.is_logged_in = True
                    self.data.update(result.get("data", {}))
        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            _LOGGER.error(f"Failed to login, Error: {ex}, Line: {tb.tb_lineno}")

        return self.is_logged_in

    async def load_camera(self):
        _LOGGER.debug("Retrieving camera list")
        response = await self.async_verified_post({"cmd": "camlist", "session": self.session_id})
        if response:
            self.camera_list = [CameraData(cam) for cam in response.get("data", [])]

        return response is not None

    async def load_status(self):
        _LOGGER.debug("Retrieving status")
        response = await self.async_verified_post({"cmd": "status", "session": self.session_id})
        if response:
            self.status.update(response.get("data", {}))

        return response is not None

    async def set_profile(self, profile_id):
        _LOGGER.debug(f"Setting profile {profile_id}")
        await self._set_profile(profile_id)

    async def _set_profile(self, profile_id, check_lock=True):
        response = await self.async_verified_post({
            "cmd": "status",
            "session": self.session_id,
            "profile": profile_id,
        })
        if response:
            data = response.get("data", {})
            if check_lock and data.get("lock") != 1:
                _LOGGER.debug(f"Holding profile change (calling twice to hold)")
                await self._set_profile(profile_id, False)
                return            
            self.status.update(data)

    async def set_schedule(self, schedule_name):
        _LOGGER.debug(f"Setting schedule {schedule_name}")
        await self._set_schedule(schedule_name)

    async def _set_schedule(self, schedule_name, check_lock=True):
        response = await self.async_verified_post({
            "cmd": "status",
            "session": self.session_id,
            "schedule": schedule_name,
        })
        if response:
            data = response.get("data", {})
            if check_lock and data.get("lock") != 1:
                await self._set_schedule(schedule_name, False)
                return
            self.status.update(data)

    async def trigger_camera(self, camera_short_name):
        _LOGGER.debug(f"Triggering camera {camera_short_name}")
        await self.async_verified_post({
            "cmd": "trigger",
            "session": self.session_id,
            "camera": camera_short_name,
        })

    async def reset_camera(self, camera_short_name):
        """Reset (reconnect) a camera via camconfig, same as BI's "Reset" action.

        Requires a Blue Iris user with admin rights. Raises BlueIrisCommandError
        with the reason when the login or the command fails, so a service call
        surfaces the problem instead of failing silently.
        """
        _LOGGER.debug(f"Resetting camera {camera_short_name}")

        if not self.is_logged_in and not await self.login():
            raise BlueIrisCommandError(
                f"Cannot reset camera {camera_short_name}: login to Blue Iris failed"
            )

        if not self.data.get("admin", False):
            raise BlueIrisCommandError(
                f"Cannot reset camera {camera_short_name}: "
                f"Blue Iris user '{self.config_data.username}' is not an admin"
            )

        result = None
        for attempt in range(2):
            result = await self.async_post({
                "cmd": "camconfig",
                "session": self.session_id,
                "camera": camera_short_name,
                "reset": True,
            })

            if result is not None and result.get("result") == "success":
                _LOGGER.debug(f"Camera {camera_short_name} reset, response: {result}")
                return

            # The session may have expired; log in again and retry once
            if attempt == 0:
                _LOGGER.debug(
                    f"Reset of {camera_short_name} failed ({result}), retrying after login"
                )
                await self.login()

        reason = None
        if result is not None:
            reason = (result.get("data") or {}).get("reason")

        raise BlueIrisCommandError(
            f"Blue Iris rejected reset of camera {camera_short_name}: "
            f"{reason or result or 'no response'}"
        )

    async def move_to_preset(self, camera_short_name, preset):
        _LOGGER.debug(f"Moving {camera_short_name} to preset {preset}")
        await self.async_verified_post({
            "cmd": "ptz",
            "session": self.session_id,
            "camera": camera_short_name,
            "button": 100 + preset,
        })
