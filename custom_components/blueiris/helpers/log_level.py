"""Read and set the integration's log level (no manager imports)."""
import logging

from .const import (
    INTEGRATION_LOGGER,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_SELECT_OPTIONS,
)


def get_log_level() -> str:
    """The level actually in effect for this integration's logger."""
    level = logging.getLogger(INTEGRATION_LOGGER).getEffectiveLevel()

    for name in LOG_LEVEL_SELECT_OPTIONS:
        if level <= getattr(logging, name.upper()):
            return name

    return LOG_LEVEL_ERROR


def set_log_level(level_name: str):
    logging.getLogger(INTEGRATION_LOGGER).setLevel(level_name.upper())
