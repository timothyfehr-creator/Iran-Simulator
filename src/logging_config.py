"""Shared logging configuration for the Iran Simulation project.

Call ``configure_logging()`` once at any CLI entry point to ensure logs are emitted.
The function is idempotent — if the root logger already has handlers, it does nothing.
"""

import logging
import os


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with console + optional file handler.

    Only configures if the root logger has no handlers (idempotent).
    """
    root = logging.getLogger()
    if root.handlers:
        return

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler (optional — only if logs/ exists or can be created)
    try:
        os.makedirs("logs", exist_ok=True)
        fh = logging.FileHandler("logs/pipeline.log", mode="a")
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError:
        pass

    root.setLevel(level)
