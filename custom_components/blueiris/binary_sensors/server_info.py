"""Read-only server information (SSL, Admin)."""
from __future__ import annotations

from homeassistant.const import EntityCategory

from .base import BlueIrisBinarySensor


class BlueIrisServerInfoBinarySensor(BlueIrisBinarySensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def icon(self):
        return self.entity.icon
