"""Stream monitoring: did each camera's stream (re)connect, and how fast.

HA's Stream.available turns True at the start of every connection attempt,
before any video arrives, so it can't tell whether a stream really works.
This watches the stream's outputs for new video segments instead: a new
segment means video is flowing.

Only streams that are open (someone watching, or preloaded) can be judged;
others are 'idle'. Statistics are kept in memory per Stream Method and start
over when Home Assistant restarts.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from ..helpers.const import *
from . import entity_manager as entity_manager_module

_LOGGER = logging.getLogger(__name__)


def _new_stats() -> dict[str, Any]:
    return {
        STREAM_EVENT_RESTART: 0,
        STREAM_EVENT_CONNECTED: 0,
        STREAM_EVENT_DROPPED: 0,
        STREAM_EVENT_FAILED: 0,
        "connect_seconds_total": 0.0,
    }


class StreamMonitor:
    def __init__(self, hass: HomeAssistant, ha):
        self._hass = hass
        self._ha = ha
        self._cameras: dict[str, Any] = {}  # camera id -> camera entity
        self._records: dict[str, dict[str, Any]] = {}
        self.stats: dict[str, dict[str, Any]] = {m: _new_stats() for m in STREAM_METHODS}
        self._unsub = None

    # ---- lifecycle -------------------------------------------------------

    @property
    def enabled(self) -> bool:
        auto_reset = self._ha.auto_reset_manager
        return auto_reset is not None and auto_reset.stream_monitoring

    def apply_enabled(self):
        """Start or stop to match the Stream Monitoring switch."""
        if self.enabled:
            self.start()
        else:
            self.stop()
            self._records.clear()

    def start(self):
        if self._unsub is None:
            self._unsub = async_track_time_interval(
                self._hass, self._async_tick, STREAM_CHECK_INTERVAL
            )

    def stop(self):
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def register(self, camera_entity):
        self._cameras[camera_entity.entity.id] = camera_entity

    def unregister(self, camera_entity):
        if self._cameras.get(camera_entity.entity.id) is camera_entity:
            self._cameras.pop(camera_entity.entity.id, None)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return entity_manager_module.utcnow()

    def _method(self) -> str:
        return self._ha.entity_manager.stream_method()

    def _record(self, camera_id: str) -> dict[str, Any]:
        return self._records.setdefault(
            camera_id,
            {
                "status": STREAM_STATUS_IDLE,
                "since": None,  # start of the current connect attempt / outage
                "reason": None,
                "sequence": None,
                "last_segment": None,
                "last_connect_seconds": None,
                "drops": 0,
                "failures": 0,
                "restarts": 0,
                "method": None,
            },
        )

    @staticmethod
    def _sequence(stream) -> Optional[int]:
        """Newest segment number of the stream's outputs, None if none open."""
        outputs = getattr(stream, "outputs", None)
        try:
            values = list(outputs().values()) if callable(outputs) else []
        except Exception:  # noqa: BLE001 - never let monitoring break a stream
            return None

        sequences = [getattr(o, "last_sequence", -1) for o in values]
        return max(sequences) if sequences else None

    def attributes(self, camera_id: str) -> dict[str, Any]:
        record = self._records.get(camera_id)
        if record is None:
            return {ATTR_STREAM_STATUS: STREAM_STATUS_IDLE}

        return {
            ATTR_STREAM_STATUS: record["status"],
            "stream_last_connect_seconds": record["last_connect_seconds"],
            "stream_restarts": record["restarts"],
            "stream_drops": record["drops"],
            "stream_failures": record["failures"],
        }

    def summary(self) -> dict[str, Any]:
        """Per Stream Method counts, for the server's Stream Health sensor."""
        result = {}

        for method, stats in self.stats.items():
            connected = stats[STREAM_EVENT_CONNECTED]
            result[method] = {
                "restarts": stats[STREAM_EVENT_RESTART],
                "connected": connected,
                "dropped": stats[STREAM_EVENT_DROPPED],
                "failed": stats[STREAM_EVENT_FAILED],
                "average_connect_seconds": None
                if not connected
                else round(stats["connect_seconds_total"] / connected, 1),
            }

        return result

    def problem_count(self) -> int:
        """Open streams that are currently not delivering video."""
        return sum(
            1
            for record in self._records.values()
            if record["status"]
            in (STREAM_STATUS_CONNECTING, STREAM_STATUS_DOWN, STREAM_STATUS_FAILED)
        )

    # ---- events ----------------------------------------------------------

    def _fire(self, camera_entity, event_type: str, record: dict, **extra):
        method = record["method"] or self._method()
        stats = self.stats.setdefault(method, _new_stats())
        stats[event_type] += 1

        seconds = extra.get("seconds")
        if event_type == STREAM_EVENT_CONNECTED and seconds is not None:
            stats["connect_seconds_total"] += seconds

        data = {
            "type": event_type,
            "camera_id": camera_entity.entity.id,
            "camera_name": camera_entity.name,
            "entity_id": camera_entity.entity_id,
            "method": method,
            "reason": record["reason"],
            **extra,
        }

        _LOGGER.info(
            f"Stream {camera_entity.entity.id}: {event_type}"
            + ("" if seconds is None else f" after {seconds} s")
            + f" ({method}, {record['reason']})"
        )
        self._hass.bus.async_fire(STREAM_EVENT, data)

        if camera_entity.hass is not None and camera_entity.entity_id:
            camera_entity.async_write_ha_state()

    @callback
    def stream_opened(self, camera_entity):
        """A new stream was created for the camera."""
        if not self.enabled:
            return

        record = self._record(camera_entity.entity.id)
        record.update(
            status=STREAM_STATUS_CONNECTING,
            since=self._now(),
            reason=STREAM_REASON_OPENED,
            method=self._method(),
            sequence=None,
        )

        if camera_entity.hass is not None and camera_entity.entity_id:
            camera_entity.async_write_ha_state()

    @callback
    def stream_restarted(self, camera_entity, reason: str):
        """The integration gave the stream a new URL."""
        if not self.enabled:
            return

        record = self._record(camera_entity.entity.id)
        record.update(
            status=STREAM_STATUS_CONNECTING,
            since=self._now(),
            reason=reason,
            method=self._method(),
            sequence=self._sequence(camera_entity.stream),
        )
        record["restarts"] += 1
        self._fire(camera_entity, STREAM_EVENT_RESTART, record)

    # ---- checks ----------------------------------------------------------

    async def _async_tick(self, _now=None):
        self.check()

    @callback
    def check(self):
        now = self._now()

        for camera_id, camera_entity in list(self._cameras.items()):
            try:
                self._check_camera(camera_entity, now)
            except Exception as ex:  # noqa: BLE001 - one camera must not stop others
                _LOGGER.debug(f"Stream check of {camera_id} failed: {ex}")

    def _check_camera(self, camera_entity, now: datetime):
        stream = camera_entity.stream
        record = self._record(camera_entity.entity.id)

        if stream is None:
            record["status"] = STREAM_STATUS_IDLE
            return

        sequence = self._sequence(stream)

        if sequence is None:
            # Stream exists but nothing is open on it: nothing to judge
            if record["status"] == STREAM_STATUS_CONNECTED:
                record["status"] = STREAM_STATUS_IDLE
            return

        if record["status"] == STREAM_STATUS_IDLE:
            # Opened before this monitor saw it (e.g. after a reload)
            record.update(
                status=STREAM_STATUS_CONNECTING,
                since=now,
                reason=STREAM_REASON_OPENED,
                method=self._method(),
                sequence=sequence,
            )
            return

        new_video = record["sequence"] is None or sequence > record["sequence"]
        if record["sequence"] is None and sequence < 0:
            new_video = False

        record["sequence"] = sequence

        if new_video:
            record["last_segment"] = now

            if record["status"] != STREAM_STATUS_CONNECTED:
                seconds = round((now - (record["since"] or now)).total_seconds(), 1)
                record.update(status=STREAM_STATUS_CONNECTED, last_connect_seconds=seconds)
                self._fire(camera_entity, STREAM_EVENT_CONNECTED, record, seconds=seconds)
            return

        if record["status"] == STREAM_STATUS_CONNECTED:
            last = record["last_segment"] or now
            if now - last >= STREAM_STALL_TIME:
                record.update(status=STREAM_STATUS_DOWN, since=last, reason=STREAM_REASON_STALLED)
                record["drops"] += 1
                self._fire(camera_entity, STREAM_EVENT_DROPPED, record)
            return

        if record["status"] in (STREAM_STATUS_CONNECTING, STREAM_STATUS_DOWN):
            if now - (record["since"] or now) >= STREAM_FAIL_TIME:
                record["status"] = STREAM_STATUS_FAILED
                record["failures"] += 1
                self._fire(
                    camera_entity,
                    STREAM_EVENT_FAILED,
                    record,
                    seconds=round((now - record["since"]).total_seconds(), 1),
                )
