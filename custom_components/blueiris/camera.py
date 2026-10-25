"""
Support for Blue Iris.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.blueiris/
"""
from abc import ABC
import asyncio
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import aiohttp
import voluptuous as vol

from homeassistant.components.camera import (
    DOMAIN as DOMAIN_CAMERA,
    Camera,
    CameraEntityFeature,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    TemplateError,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .helpers.const import (
    BI_CAMERA_ATTR_AUDIO_SUPPORT,
    BI_CAMERA_ATTR_GROUP_CAMERAS,
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_STREAM,
    DOMAIN,
    NOT_AVAILABLE,
    SERVICE_CURRENT_CAMERA_SNAPSHOT,
    SERVICE_MOVE_TO_PRESET,
    SERVICE_RESET_CAMERA,
    SERVICE_SNAPSHOT_FILENAME,
    SERVICE_SNAPSHOT_TO_DATABASE,
    SERVICE_TRIGGER_CAMERA,
    SNAPSHOT_MEDIA_FOLDER,
    STREAM_METHOD_FIXED,
    STREAM_METHOD_LOGIN,
    STREAM_METHOD_SESSION_AUDIO,
    STREAM_REASON_METHOD,
    STREAM_REASON_SESSION,
    STREAM_VIDEO,
)
from .api.blue_iris_api import BlueIrisCommandError
from .models.base_entity import BlueIrisEntity, async_setup_base_entry
from .models.entity_data import EntityData

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)

CURRENT_DOMAIN = DOMAIN_CAMERA


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the BlueIris Camera."""
    await async_setup_base_entry(
        hass, config_entry, async_add_devices, CURRENT_DOMAIN, get_camera
    )
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_TRIGGER_CAMERA,
        {},
        SERVICE_TRIGGER_CAMERA,
    )
    platform.async_register_entity_service(
        SERVICE_MOVE_TO_PRESET,
        {
            vol.Required("preset"): cv.positive_int,
        },
        SERVICE_MOVE_TO_PRESET,
    )
    platform.async_register_entity_service(
        SERVICE_RESET_CAMERA,
        {},
        SERVICE_RESET_CAMERA,
    )
    platform.async_register_entity_service(
        SERVICE_SNAPSHOT_TO_DATABASE,
        {},
        SERVICE_SNAPSHOT_TO_DATABASE,
    )
    platform.async_register_entity_service(
        SERVICE_CURRENT_CAMERA_SNAPSHOT,
        {
            vol.Optional(SERVICE_SNAPSHOT_FILENAME): cv.string,
        },
        SERVICE_CURRENT_CAMERA_SNAPSHOT,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_entry(_hass, config_entry):
    _LOGGER.debug(f"async_unload_entry {CURRENT_DOMAIN}: {config_entry}")

    return True


JPEG_MAGIC = b"\xff\xd8"


def _snapshot_filename(camera_id: str, filename: Optional[str]) -> str:
    """Return a safe file name inside the snapshot folder."""
    name = Path(filename).name if filename else ""

    if not name or name in (".", ".."):
        name = f"{camera_id.lower()}_current.jpg"

    if not Path(name).suffix:
        name = f"{name}.jpg"

    return name


def _save_image(path: Path, image: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)


def get_camera(hass: HomeAssistant, host: str, entity: EntityData):
    device_info = entity.details

    camera = BlueIrisCamera(hass, device_info)
    camera.initialize(hass, host, entity, CURRENT_DOMAIN)

    return camera


class BlueIrisCamera(Camera, BlueIrisEntity, ABC):
    """BlueIris Camera"""

    def __init__(self, hass, device_info):
        super().__init__()
        self.hass = hass

        stream_source = device_info.get(CONF_STREAM_SOURCE)
        stream_support = device_info.get(CONF_SUPPORT_STREAM, False)

        

        self._still_image_url = device_info[CONF_STILL_IMAGE_URL]
        self._still_image_url.hass = hass

        self._stream_source = device_info[CONF_STREAM_SOURCE]
        self._limit_refetch = device_info[CONF_LIMIT_REFETCH_TO_URL_CHANGE]
        self._frame_interval = 1 / device_info[CONF_FRAMERATE]        
        self.content_type = device_info[CONF_CONTENT_TYPE]
        self.verify_ssl = device_info[CONF_VERIFY_SSL]

        self._attr_supported_features = CameraEntityFeature(0)
        if stream_source and stream_support:            
            self._attr_supported_features = CameraEntityFeature.STREAM

        username = device_info.get(CONF_USERNAME)
        password = device_info.get(CONF_PASSWORD)

        if username and password:
            self._auth = aiohttp.BasicAuth(username, password=password)
        else:
            self._auth = None

        self._last_url = None
        self._last_image = None

    def _immediate_update(self, previous_state: bool):
        if previous_state != self.entity.state:
            _LOGGER.debug(
                f"{self.name} updated from {previous_state} to {self.entity.state}"
            )

        self._apply_stream_source()

        super()._immediate_update(previous_state)

    @property
    def _stream_method(self) -> str:
        return self.entity_manager.stream_method()

    def _session_url(self, path: str) -> str:
        return f"{self.api.base_url}/{path}?session={self.api.session_id}"

    def _login_url(self, path: str) -> Optional[str]:
        """http://user:password@host:port/path, or None without a login."""
        config_data = self.ha.config_data
        username = config_data.username
        password = config_data.password_clear_text

        if not username or not password:
            return None

        scheme, rest = self.api.base_url.split("://", 1)
        login = f"{quote(username, safe='')}:{quote(password, safe='')}"

        return f"{scheme}://{login}@{rest}/{path}"

    def current_stream_source(self) -> Optional[str]:
        """Stream URL for the selected Stream Method."""
        method = self._stream_method

        if method == STREAM_METHOD_FIXED or not self._stream_source:
            return self._stream_source

        video = STREAM_VIDEO.get(self.ha.config_data.stream_type, {})
        path = f"{video.get('stream_name')}/{self.entity.id}/{video.get('file_name', '')}"

        if method == STREAM_METHOD_LOGIN:
            login_url = self._login_url(path)
            if login_url is not None:
                return login_url
            # No username / password configured: nothing to put in the URL

        url = self._session_url(path)

        has_audio = self.entity.attributes.get(BI_CAMERA_ATTR_AUDIO_SUPPORT) is True
        if method == STREAM_METHOD_SESSION_AUDIO and has_audio:
            url = f"{url}&audio=1"

        return url

    def _apply_stream_source(self):
        """Restart a running stream when its URL should change.

        Follow session: the Blue Iris session changed (new login). Any
        method: the Stream Method was switched.
        """
        method = self._stream_method
        method_changed = method != getattr(self, "_last_method", method)
        self._last_method = method

        # Fixed URL never touches a running stream, as before Stream Method
        # existed, except once when switching to it from another method
        if method == STREAM_METHOD_FIXED and not method_changed:
            return

        stream = self.stream
        new_source = self.current_stream_source()

        if stream is None or new_source is None or stream.source == new_source:
            return

        _LOGGER.debug(f"{self.name}: stream source changed ({method})")
        stream.update_source(new_source)
        self.entity_manager.stream_restarts += 1

        if self.ha.stream_monitor is not None:
            self.ha.stream_monitor.stream_restarted(
                self, STREAM_REASON_METHOD if method_changed else STREAM_REASON_SESSION
            )

    async def async_added_to_hass_local(self):
        """Subscribe MQTT events."""
        _LOGGER.debug(f"Added new {self.name}")
        self._last_method = self._stream_method
        if self.ha.stream_monitor is not None:
            # Only a reference; nothing runs while monitoring is off
            self.ha.stream_monitor.register(self)

    async def async_will_remove_from_hass_local(self):
        if self.ha.stream_monitor is not None:
            self.ha.stream_monitor.unregister(self)

    def _monitoring(self) -> bool:
        monitor = None if self.ha is None else self.ha.stream_monitor
        return monitor is not None and monitor.enabled

    async def async_create_stream(self):
        """Create the stream; with monitoring on, report a new one."""
        if not self._monitoring():
            return await super().async_create_stream()

        previous = self.stream
        stream = await super().async_create_stream()

        if stream is not None and stream is not previous:
            self.ha.stream_monitor.stream_opened(self)

        return stream

    @property
    def extra_state_attributes(self):
        if not self._monitoring():
            return self.entity.attributes

        attributes = dict(self.entity.attributes)
        attributes.update(self.ha.stream_monitor.attributes(self.entity.id))

        return attributes

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Return supported features for this camera."""
        return self._attr_supported_features

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return self._frame_interval

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of camera image."""
        return asyncio.run_coroutine_threadsafe(
            self.async_camera_image(), self.hass.loop
        ).result()

    async def async_camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return a still image response from the camera."""
        try:
            if self._stream_method == STREAM_METHOD_FIXED:
                url = self._still_image_url.async_render()
            elif self._stream_method == STREAM_METHOD_LOGIN and self._auth is not None:
                # Basic auth header (self._auth), no session in the URL
                url = f"{self.api.base_url}/image/{self.entity.id}"
            else:
                url = self._session_url(f"image/{self.entity.id}")
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        if url == self._last_url and self._limit_refetch:
            return self._last_image

        try:
            websession = async_get_clientsession(self.hass, verify_ssl=self.verify_ssl)

            response = await websession.get(url, auth=self._auth, timeout=10)

            self._last_image = await response.read()
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting camera image from %s", self.name)
            return self._last_image
        except aiohttp.ClientError as err:
            _LOGGER.error("Error getting new camera image from %s: %s", self.name, err)
            return self._last_image

        self._last_url = url
        return self._last_image

    async def stream_source(self):
        """Return the source of the stream."""
        return self.current_stream_source()

    async def trigger_camera(self):
        if self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS] == NOT_AVAILABLE:
            await self.api.trigger_camera(self.entity.id)
        else:
            for grouped_camera in self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS]:
                await self.api.trigger_camera(grouped_camera)

    async def move_to_preset(self, preset):
        if self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS] == NOT_AVAILABLE:
            await self.api.move_to_preset(self.entity.id, preset)
        else:
            for grouped_camera in self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS]:
                await self.api.move_to_preset(grouped_camera, preset)

    async def reset_camera(self):
        # A group has no connection of its own; resetting every member at
        # once would drop all of their streams, so require a real camera.
        if self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS] != NOT_AVAILABLE:
            raise ServiceValidationError(
                f"{self.name} is a camera group; reset_camera needs a single camera"
            )

        try:
            await self.api.reset_camera(self.entity.id)
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex

    async def snapshot_to_database(self):
        """Save a snapshot into Blue Iris' own clips database."""
        if self.entity.attributes[BI_CAMERA_ATTR_GROUP_CAMERAS] != NOT_AVAILABLE:
            raise ServiceValidationError(
                f"{self.name} is a camera group; snapshot_to_database needs a single camera"
            )

        try:
            await self.api.snapshot_to_database(self.entity.id)
        except BlueIrisCommandError as ex:
            _LOGGER.error(str(ex))
            raise HomeAssistantError(str(ex)) from ex

    async def current_camera_snapshot(self, filename: Optional[str] = None):
        """Save the current still image to the local media folder."""
        image = await self.async_camera_image()

        # async_camera_image does not check the HTTP status, so an error page
        # (e.g. 401) would come back as the "image"; only accept a JPEG.
        if not image or not image.startswith(JPEG_MAGIC):
            raise HomeAssistantError(
                f"Unable to fetch a snapshot from Blue Iris for {self.name}"
            )

        name = _snapshot_filename(self.entity.id, filename)

        media_root = self.hass.config.media_dirs.get("local") or self.hass.config.path(
            "media"
        )
        path = Path(media_root) / SNAPSHOT_MEDIA_FOLDER / name

        await self.hass.async_add_executor_job(_save_image, path, image)

        _LOGGER.debug(f"Saved snapshot of {self.name} to {path}")

        return {
            "camera_id": self.entity.id,
            "camera_name": self.entity.attributes.get(CONF_NAME, self.name),
            "saved_filename": name,
            "saved_path": str(path),
            "local_snapshot_url": f"/media/local/{SNAPSHOT_MEDIA_FOLDER}/{name}",
            "generated_at": dt_util.utcnow().isoformat(),
        }
