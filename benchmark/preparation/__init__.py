from collections import Counter
from typing import Protocol

from benchmark.preparation.batch import Batch
from benchmark.preparation.cases import get_cases


class Backend(Protocol):
    """Interface of an arbitrary quantum processing backend."""

    def __init__(): ...

    def run(self, circuit: str) -> Counter:
        """Run the circuit and return its bitstring distribution.

        Args:
            circuit (str): a circuit in OpenQASM format
        """


from benchmark.preparation.scheduler import Scheduler, get_scheduler


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


__all__ = [
    "Backend",
    "Batch",
    "Scheduler",
    "get_backend",
    "get_cases",
    "get_scheduler",
]
