"""
Per-camera Problem binary sensor, computed from Blue Iris' camera list.
"""
from __future__ import annotations

from ..helpers.const import *
from .base import BlueIrisBinarySensor


class BlueIrisProblemBinarySensor(BlueIrisBinarySensor):
    """On when a camera has no signal, is offline or has stalled.

    Unavailable while the server is unreachable, the last poll failed or
    Blue Iris has only just started, so stale or settling data never turns
    it on.
    """

    @property
    def available(self) -> bool:
        return self.entity.details.get(ENTITY_AVAILABLE, False)
