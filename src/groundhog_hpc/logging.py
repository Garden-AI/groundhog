"""Logging configuration for Groundhog HPC.

This module provides centralized logging setup with support for:
- Hierarchical per-module loggers (groundhog.compute, groundhog.serialization, etc.)
- Environment variable configuration (GROUNDHOG_LOG_LEVEL)
- CLI flag overrides
- Remote log level propagation
"""

import logging
import os
import sys


def setup_logging() -> None:
    """Configure the root groundhog logger.

    Reads log level from GROUNDHOG_LOG_LEVEL environment variable.
    Defaults to WARNING if not set.

    Valid log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

    Can be called multiple times to reconfigure the log level.
    """
    level_name = os.getenv("GROUNDHOG_LOG_LEVEL", "WARNING").upper()

    # Convert string to logging level, default to WARNING if invalid
    level = getattr(logging, level_name, logging.WARNING)

    # Configure root groundhog logger
    logger = logging.getLogger("groundhog_hpc")
    logger.setLevel(level)

    # Add stderr handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        # Update level on existing handlers
        for handler in logger.handlers:
            handler.setLevel(level)

    # Allow propagation to parent loggers (enables pytest caplog capture)
    # This won't cause duplicate logs unless the root logger also has handlers,
    # which is rare in production but common in tests
    logger.propagate = True
