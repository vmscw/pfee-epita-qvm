"""Logging of ultraq: one level for the whole package, set by `ULTRAQ_LOG_LEVEL`.

`setup_logging()` runs once, when `ultraq_backend` is imported. It reads
`ULTRAQ_LOG_LEVEL` (environment, else a `.env` file at or above the current
directory, which is only read, not loaded into the environment; `DEBUG`,
`INFO`, `WARNING` or `ERROR`, default `INFO` when unset or empty) and gives
the loggers `ultraq_backend` and `ultraq_qiskit_connector` that level and a
console handler. Every module logs through `logging.getLogger(__name__)`.

Only ultraq's own loggers are configured: the root logger and the libraries
(qiskit, iqm-client...) keep Python's default behaviour. ultraq's loggers do
not propagate to the root logger, so a user's own logging configuration
neither duplicates nor changes ultraq's lines.

Level convention: DEBUG = details (per-job decisions, mapping, composite
circuit, count split, HTTP requests); INFO = life cycle (hypervisor
start/stop, job submitted/finished, batch run and its duration, backend job
id, calibration fetched/loaded); WARNING = anomalies that do not fail
(missing metrics); ERROR = failures (a job that fails, including one that
can never be placed), with the traceback once, where it is caught.
Never log a token or any other value read from `.env`.
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import dotenv_values, find_dotenv

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
LOGGERS = ("ultraq_backend", "ultraq_qiskit_connector")
"""ultraq's top-level loggers (by name: the core never imports the connector)."""

FORMAT = "%(asctime)s %(levelname)-7s %(name)s [%(threadName)s] %(message)s"
DATE_FORMAT = "%H:%M:%S"

_setup_done = False


def setup_logging() -> None:
    """Configure ultraq's loggers from `ULTRAQ_LOG_LEVEL` (once; later calls do nothing).

    Raises ValueError if the variable holds something other than DEBUG,
    INFO, WARNING or ERROR (case-insensitive).
    """
    global _setup_done
    if _setup_done:
        return
    raw = os.environ.get("ULTRAQ_LOG_LEVEL")
    if raw is None:  # read `.env` without loading it: tokens stay out of os.environ until needed
        raw = dotenv_values(find_dotenv(usecwd=True)).get("ULTRAQ_LOG_LEVEL")
    level = (raw or "").strip().upper() or "INFO"
    if level not in LEVELS:
        raise ValueError(f"ULTRAQ_LOG_LEVEL={raw!r} is not a log level, expected one of {', '.join(LEVELS)}")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
    for name in LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        logger.propagate = False
    _setup_done = True
