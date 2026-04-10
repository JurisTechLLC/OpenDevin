"""Logging configuration for OttoSoftwareEngineer.

Provides a centralized logger with structured JSON output,
consistent with the Devin.ai logging patterns.
"""

import logging
import sys


def get_logger(name: str = "otto") -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name, defaults to 'otto'.

    Returns:
        A configured logging.Logger instance.
    """
    log = logging.getLogger(name)

    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    return log


otto_logger = get_logger("otto")
