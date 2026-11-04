from collections.abc import Sequence
from typing import Type, Any


class Backend:
    pass


class Scheduler:
    pass


def get_cases() -> list[list[str]]:
    """Return the benchmark cases.

    Returns:
        list[list[str]]: A list of batchs containing circuits in OpenQASM
                         format.
    """
    return []


def get_backend(name: str) -> Backend:
    """Return a backend matching the specified backend.

    A backend is the engine processing the circuits once compiled by the
    scheduler.

    Args:
        name (str): a name

    Returns:
        Backend: The corresponding backend.

    Raises:
        ValueError: if the specified name doesn't correspond to any actual
                    backend
    """
    raise NotImplementedError


def get_scheduler(name: str, *, backend: Backend) -> Scheduler:
    """Return a scheduler to benchmark based on its name.

    Args:
        name (str): a name
        backend (Backend): a backend to provide to the scheduler

    Returns:
        Scheduler: The corresponding scheduler.

    Raises:
        ValueError: if the specified name doesn't correspond to any actual
                    scheduler
    """
    raise NotImplementedError


__all__ = [
    "get_backend",
    "get_cases",
    "get_scheduler",
]
