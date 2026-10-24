"""Auto reset: reset cameras whose Problem sensor stays on.

Level-based on purpose: every successful poll looks at how long each camera
has had a problem and how many resets it already got, so nothing depends on
catching a single state change (and an HA restart just starts over).

Settings are per camera (enabled, delay, attempts, interval) plus two server
flags, kept in the integration's own storage and changed live through
switch / number entities.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Optional

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..api.blue_iris_api import BlueIrisCommandError
from ..helpers.const import *
from .configuration_manager import clean_auto_reset_values
from . import entity_manager as entity_manager_module

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 5  # seconds; coalesces quick slider changes


class AutoResetManager:
    def __init__(self, hass: HomeAssistant, ha):
        self._hass = hass
        self._ha = ha
        self._store: Optional[Store] = None
        self._settings: dict[str, Any] = self._default_settings()
        # Runtime state per camera id, not stored: an HA restart starts over
        self._runtime: dict[str, dict[str, Any]] = {}

    # ---- settings -------------------------------------------------------

    @staticmethod
    def _default_settings() -> dict[str, Any]:
        return {
            AUTO_RESET_KEY_ENABLED: True,
            AUTO_RESET_KEY_NOTIFICATIONS: True,
            AUTO_RESET_KEY_CAMERAS: {},
            KEY_PROBLEM_DETECTION_OFF: [],
        }

    async def async_load(self, entry_id: str):
        self._store = Store(
            self._hass, STORAGE_VERSION, f"{DOMAIN}.auto_reset.{entry_id}"
        )
        stored = await self._store.async_load()

        settings = self._default_settings()
        if isinstance(stored, dict):
            for key in (AUTO_RESET_KEY_ENABLED, AUTO_RESET_KEY_NOTIFICATIONS):
                if isinstance(stored.get(key), bool):
                    settings[key] = stored[key]

            cameras = stored.get(AUTO_RESET_KEY_CAMERAS)
            if isinstance(cameras, dict):
                settings[AUTO_RESET_KEY_CAMERAS] = {
                    str(cam_id): self._clean_camera_settings(values)
                    for cam_id, values in cameras.items()
                    if isinstance(values, dict)
                }

            detection_off = stored.get(KEY_PROBLEM_DETECTION_OFF)
            if isinstance(detection_off, list):
                settings[KEY_PROBLEM_DETECTION_OFF] = [
                    str(cam_id) for cam_id in detection_off
                ]

        self._settings = settings

    def _save(self):
        if self._store is not None:
            self._store.async_delay_save(lambda: self._settings, SAVE_DELAY)

    @staticmethod
    def _clean_camera_settings(values: dict) -> dict[str, Any]:
        """Keep only valid per-camera overrides."""
        return clean_auto_reset_values(values, {})

    @property
    def enabled(self) -> bool:
        return self._settings[AUTO_RESET_KEY_ENABLED]

    @property
    def notifications(self) -> bool:
        return self._settings[AUTO_RESET_KEY_NOTIFICATIONS]

    def set_flag(self, key: str, value: bool):
        self._settings[key] = bool(value)
        self._save()

    @property
    def defaults(self) -> dict[str, Any]:
        config_data = self._ha.config_data
        if config_data is None:
            return dict(AUTO_RESET_CAMERA_DEFAULTS)

        return dict(config_data.auto_reset_defaults)

    def camera_settings(self, camera_id: str) -> dict[str, Any]:
        """Defaults from the options, with this camera's own values on top."""
        settings = self.defaults
        settings.update(self._settings[AUTO_RESET_KEY_CAMERAS].get(camera_id, {}))

        return settings

    def set_camera_value(self, camera_id: str, key: str, value):
        cameras = self._settings[AUTO_RESET_KEY_CAMERAS]
        overrides = dict(cameras.get(camera_id, {}))
        overrides[key] = value
        cameras[camera_id] = self._clean_camera_settings(overrides)
        self._save()

    def problem_detection(self, camera_id: str) -> bool:
        return camera_id not in self._settings[KEY_PROBLEM_DETECTION_OFF]

    def set_problem_detection(self, camera_id: str, enabled: bool):
        off = [c for c in self._settings[KEY_PROBLEM_DETECTION_OFF] if c != camera_id]
        if not enabled:
            off.append(camera_id)

        self._settings[KEY_PROBLEM_DETECTION_OFF] = off
        # Turning detection off ends any reset cycle without a 'recovered'
        self._runtime.pop(camera_id, None)
        self._save()

    def reset_cameras_to_defaults(self):
        """Forget every camera's own values so all follow the defaults."""
        _LOGGER.info("Auto reset: all cameras set back to the defaults")
        self._settings[AUTO_RESET_KEY_CAMERAS] = {}
        self._save()

    # ---- runtime --------------------------------------------------------

    def _rt(self, camera_id: str) -> dict[str, Any]:
        return self._runtime.setdefault(
            camera_id,
            {"state": AUTO_RESET_STATE_IDLE, "attempts": 0, "last_reset": None},
        )

    def status(self, camera_id: str) -> dict[str, Any]:
        """Attributes for the camera's Problem sensor."""
        settings = self.camera_settings(camera_id)
        rt = self._runtime.get(camera_id)

        if not settings[AUTO_RESET_KEY_ENABLED] or not self.problem_detection(camera_id):
            state = AUTO_RESET_STATE_OFF
        elif not self.enabled or not self._ha.entity_manager.problem_data_fresh:
            state = AUTO_RESET_STATE_PAUSED
        else:
            state = AUTO_RESET_STATE_IDLE if rt is None else rt["state"]

        last_reset = None if rt is None else rt["last_reset"]

        return {
            ATTR_AUTO_RESET_STATE: state,
            ATTR_AUTO_RESET_ATTEMPTS: 0 if rt is None else rt["attempts"],
            ATTR_AUTO_RESET_LAST: None if last_reset is None else last_reset.isoformat(),
        }

    async def async_evaluate(self, now: Optional[datetime] = None):
        """Run once after every poll."""
        entity_manager = self._ha.entity_manager

        # Never act on stale or settling data, or while paused
        if not self.enabled or not entity_manager.problem_data_fresh:
            return

        if not self._ha.api.data.get("admin", False):
            return

        now = now or entity_manager_module.utcnow()

        for camera in self._ha.api.camera_list:
            if not camera.is_physical:
                continue

            if not entity_manager.is_problem_sensor_allowed(camera):
                continue

            settings = self.camera_settings(camera.id)

            if not settings[AUTO_RESET_KEY_ENABLED] or not self.problem_detection(
                camera.id
            ):
                self._runtime.pop(camera.id, None)
                continue

            try:
                await self._async_evaluate_camera(camera, settings, now)
            except Exception as ex:  # one camera must not stop the others
                _LOGGER.error(f"Auto reset failed for {camera.id}: {ex}")

    async def _async_evaluate_camera(self, camera, settings: dict, now: datetime):
        entity_manager = self._ha.entity_manager
        problem = entity_manager.camera_problems.get(camera.id)
        since = entity_manager.problem_since.get(camera.id)
        rt = self._rt(camera.id)

        if problem is None:
            if rt["attempts"] > 0:
                self._finish(camera, rt, AUTO_RESET_EVENT_RECOVERED, now)
            self._runtime.pop(camera.id, None)
            return

        if since is None:
            return

        delay = timedelta(seconds=settings[AUTO_RESET_KEY_DELAY])
        interval = timedelta(seconds=settings[AUTO_RESET_KEY_INTERVAL])
        max_attempts = int(settings[AUTO_RESET_KEY_ATTEMPTS])

        if now - since < delay:
            rt["state"] = AUTO_RESET_STATE_WAITING
            return

        last_reset = rt["last_reset"]
        due = last_reset is None or now - last_reset >= interval

        if rt["attempts"] >= max_attempts:
            if due and rt["state"] != AUTO_RESET_STATE_GAVE_UP:
                self._finish(camera, rt, AUTO_RESET_EVENT_GAVE_UP, now)
            return

        if not due:
            return

        rt["attempts"] += 1
        rt["last_reset"] = now
        rt["state"] = AUTO_RESET_STATE_RESETTING

        error = None
        try:
            await self._ha.api.reset_camera(camera.id)
        except BlueIrisCommandError as ex:
            error = str(ex)
            _LOGGER.warning(f"Auto reset of {camera.id} failed: {error}")

        _LOGGER.info(
            f"Auto reset {camera.id} ({problem}), attempt {rt['attempts']} of {max_attempts}"
        )

        self._fire(camera, AUTO_RESET_EVENT_RESET, rt, max_attempts, error)
        self._notify(
            camera,
            f"Resetting the camera: attempt {rt['attempts']} of {max_attempts}"
            + ("" if error is None else f" (failed: {error})"),
            title_suffix="problem",
        )

    def _finish(self, camera, rt: dict, event_type: str, now: datetime):
        attempts = rt["attempts"]
        settings = self.camera_settings(camera.id)
        when = dt_util.as_local(now).strftime("%Y-%m-%d %H:%M:%S")

        if event_type == AUTO_RESET_EVENT_RECOVERED:
            rt["state"] = AUTO_RESET_STATE_IDLE
            text = f"**Recovered:** {when} after {attempts} reset(s)"
            suffix = "recovered"
        else:
            rt["state"] = AUTO_RESET_STATE_GAVE_UP
            text = f"**Status:** still down after {attempts} reset(s) ({when})"
            suffix = "still down"

        self._fire(camera, event_type, rt, int(settings[AUTO_RESET_KEY_ATTEMPTS]))
        self._notify(camera, text, title_suffix=suffix)

    # ---- output ---------------------------------------------------------

    def _camera_entity_id(self, camera) -> Optional[str]:
        entity_manager = self._ha.entity_manager
        unique_id = (
            f"{DOMAIN}-{DOMAIN_CAMERA}-{entity_manager.integration_title} {camera.name}"
        )
        return entity_manager.entity_registry.async_get_entity_id(
            DOMAIN_CAMERA, DOMAIN, unique_id
        )

    def _problem_text(self, camera) -> tuple[str, str]:
        entity_manager = self._ha.entity_manager
        reason = entity_manager.camera_problems.get(camera.id)
        since = entity_manager.problem_since.get(camera.id)

        reason_text = (reason or "unknown").replace("_", " ")
        since_text = (
            "unknown"
            if since is None
            else dt_util.as_local(since).strftime("%Y-%m-%d %H:%M:%S")
        )

        return reason_text, since_text

    def _fire(self, camera, event_type: str, rt: dict, max_attempts: int, error=None):
        entity_manager = self._ha.entity_manager
        since = entity_manager.problem_since.get(camera.id)

        self._hass.bus.async_fire(
            AUTO_RESET_EVENT,
            {
                "type": event_type,
                "camera_id": camera.id,
                "camera_name": camera.name,
                "entity_id": self._camera_entity_id(camera),
                "reason": entity_manager.camera_problems.get(camera.id)
                or entity_manager.last_problem.get(camera.id),
                "since": None if since is None else since.isoformat(),
                "attempt": rt["attempts"],
                "max_attempts": max_attempts,
                "error": error,
            },
        )

    def _notify(self, camera, status_line: str, title_suffix: str):
        if not self.notifications:
            return

        entity_manager = self._ha.entity_manager
        reason, since_text = self._problem_text(camera)

        if reason == "unknown":
            # Recovered: the problem is already cleared, show what it was
            last = entity_manager.last_problem.get(camera.id)
            if last is not None:
                reason = last.replace("_", " ")
            last_since = entity_manager.last_problem_since.get(camera.id)
            if last_since is not None:
                since_text = dt_util.as_local(last_since).strftime("%Y-%m-%d %H:%M:%S")

        title_name = f"{entity_manager.integration_title} {camera.name}"

        persistent_notification.async_create(
            self._hass,
            f"**Camera:** {camera.name} ({camera.id})\n"
            f"**Problem:** {reason}\n"
            f"**Since:** {since_text}\n\n"
            f"{status_line}",
            title=f"Blue Iris: {title_name} {title_suffix}",
            notification_id=f"{DOMAIN}_auto_reset_{camera.id}",
        )
