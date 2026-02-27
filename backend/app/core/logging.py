"""One-time logging configuration for the app."""
import logging
import sys
from typing import Optional


def setup_logging(
    name: str = "app",
    level: int = logging.INFO,
    format_string: Optional[str] = None,
) -> None:
    """Configure the app logger once. Safe to call multiple times; skips if already configured."""
    log = logging.getLogger(name)
    if log.handlers:
        return
    log.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        format_string
        or "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    log.addHandler(handler)
