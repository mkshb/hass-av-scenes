"""Temporary debug log helper for the AV Scenes integration.

Usage
-----
1. Enable: add this line at the end of ``async_setup_entry`` in ``__init__.py``::

       from .debug_log import enable_debug_log
       enable_debug_log(hass)

2. Disable: remove (or comment out) the two lines above and restart HA.

The log file is written to ``<config_dir>/av_scenes_debug.log`` (max 2 × 1 MB,
rolling).  All loggers in the ``custom_components.av_scenes`` namespace are
captured at DEBUG level, regardless of the global HA log level.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_INTEGRATION_LOGGER_PREFIX = "custom_components.av_scenes"
_HANDLER_ATTR = "_av_scenes_debug_handler"

_FMT = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-8s  %(name)s  —  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def enable_debug_log(hass: HomeAssistant, filename: str = "av_scenes_debug.log") -> None:
    """Attach a rotating file handler to the integration root logger.

    Safe to call multiple times — attaches at most one handler.
    """
    root_logger = logging.getLogger(_INTEGRATION_LOGGER_PREFIX)

    # Avoid duplicate handlers on reload
    if getattr(root_logger, _HANDLER_ATTR, None) is not None:
        return

    log_path = os.path.join(hass.config.config_dir, filename)
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1 * 1024 * 1024,  # 1 MB per file
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(_FMT)
    handler.setLevel(logging.DEBUG)

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    # Keep a reference so disable_debug_log() can find it again
    setattr(root_logger, _HANDLER_ATTR, handler)

    root_logger.info(
        "av_scenes debug log enabled → %s",
        log_path,
    )


def disable_debug_log() -> None:
    """Remove the file handler added by ``enable_debug_log``."""
    root_logger = logging.getLogger(_INTEGRATION_LOGGER_PREFIX)
    handler: logging.Handler | None = getattr(root_logger, _HANDLER_ATTR, None)

    if handler is None:
        return

    root_logger.info("av_scenes debug log disabled")
    root_logger.removeHandler(handler)
    handler.close()
    setattr(root_logger, _HANDLER_ATTR, None)
