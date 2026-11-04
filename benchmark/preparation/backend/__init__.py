from collections import Counter
from typing import Protocol, Type


class Backend(Protocol):
    """Interface of an arbitrary quantum processing backend."""

    def __init__(self): ...

    def run(self, circuit: str) -> Counter:
        """Run the circuit and return its bitstring distribution.

        Args:
            circuit (str): a circuit in OpenQASM format
        """


from benchmark.preparation.backend.iqm_garnet_20q import IQMGarnet20q
from benchmark.preparation.backend.iqm_garnet_20q_emulation import (
    IQMGarnet20qEmulation,
)
from benchmark.preparation.backend.iqm_emerald_54q import IQMEmerald54q


BACKEND_NAMES: dict[str, Type[Backend]] = {
    "IQMGarnet20q": IQMGarnet20q,
    "IQMGarnet20qEmulation": IQMGarnet20qEmulation,
    "IQMEmerald54q": IQMEmerald54q,
    "iqm_garnet_20q": IQMGarnet20q,
    "iqm_garnet_20q_emulation": IQMGarnet20qEmulation,
    "iqm_emerald_54q": IQMEmerald54q,
}


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
    backend_type = BACKEND_NAMES.get(name, None)

    if backend_type is None:
        raise ValueError(f"{name} doesn't refer to any backend type")

    return backend_type()


__all__ = [
    "Backend",
    "IQMGarnet20q",
    "IQMGarnet20qEmulation",
    "IQMEmerald54q",
    "get_backend",
]
