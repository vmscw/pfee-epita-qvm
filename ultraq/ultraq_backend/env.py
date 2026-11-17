"""Environment variables: read one, after loading the `.env` file.

The `.env` file is looked up at or above the current directory. This module
must not know which variables exist nor what they are for: callers pass the
name (e.g. `IQM_URL`). Never log or print a value read here.
"""

from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv


def from_env(name: str, what: str) -> str:
    """Environment variable `name` (`.env` at or above the current directory
    loaded first, without overriding variables already set); RuntimeError
    naming `what` if not set or empty. The value never appears in the error."""
    load_dotenv(find_dotenv(usecwd=True))
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"No {what}: set the {name} environment variable "
            f"or put {name}=... in a .env file at or above the current directory."
        )
    return value
