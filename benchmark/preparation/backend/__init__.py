from collections import Counter
from typing import Protocol, Type

from qiskit import QuantumCircuit
from qiskit.providers import BackendV2 as QiskitBackend, JobV1


class Backend(Protocol):
    """Interface of an arbitrary quantum processing backend."""

    name: str
    """Name of the backend."""
    num_qubits: int
    """The total number of qubits of the backend."""
    architecture: QiskitBackend
    """The underlying architecture of the computation backend.

    This is required for schedulers that do not do their own circuit
    transpilation.
    """

    def __init__(self): ...

    def run(self, circuit: QuantumCircuit, shots: int, **kwargs) -> JobV1:
        """Run the circuit and return a job id.

        The circuit MUST be transpiled for the backend architecture beforehand.

        Args:
            circuit (str): a pre-transpiled circuit
            shots (int): a number of shots
            kwargs: extra arguments that will be passed upon the call to
                    qiskit.providers.Backend.run

        Returns:
            JobV1 | None: The job running the circuit.
        """


from benchmark.preparation.backend.iqm_garnet_20q import IQMGarnet20q
from benchmark.preparation.backend.iqm_garnet_20q_emulation import (
    IQMGarnet20qEmulation,
)
from benchmark.preparation.backend.iqm_emerald_54q import IQMEmerald54q
from benchmark.preparation.backend.scaleway_base import ScalewayProvided
from benchmark.preparation.backend.qiskit_aer import QiskitAer
from benchmark.preparation.backend.qiskit_aer_scaleway import QiskitAerScaleway


BACKEND_NAMES: dict[str, Type[Backend]] = {
    "IQMGarnet20q": IQMGarnet20q,
    "IQMGarnet20qEmulation": IQMGarnet20qEmulation,
    "IQMEmerald54q": IQMEmerald54q,
    "QiskitAer": QiskitAer,
    "QiskitAerScaleway": QiskitAerScaleway,
    "iqm_garnet_20q": IQMGarnet20q,
    "iqm_garnet_20q_emulation": IQMGarnet20qEmulation,
    "iqm_emerald_54q": IQMEmerald54q,
    "qiskit_aer": QiskitAer,
    "qiskit_aer_scaleway": QiskitAerScaleway,
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
    "QiskitAer",
    "ScalewayProvided",
    "get_backend",
]
