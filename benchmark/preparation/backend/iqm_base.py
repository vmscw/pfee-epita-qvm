from abc import ABC

from iqm.qiskit_iqm import IQMBackend, IQMJob, IQMProvider
from iqm.qiskit_iqm.iqm_backend import IQMBackendBase
from qiskit import QuantumCircuit
from qiskit.providers import BackendV2, JobV1

from benchmark.config import invoke_config, invoke_auth_config
from benchmark.utils import qasm2_to_qiskit


class IQMProvided(ABC):
    """Abstract structure for any backend provided by IQM.

    Args:
        name (str): name of the computer to invoke from the IQM provider
    """

    def __init__(self, name: str):
        auth_config = invoke_auth_config()

        self._provider: IQMProvider | None = IQMProvider(
            url=auth_config.IQM_SERVER_URL + name,
            quantum_computer=name,
            token=auth_config.IQM_TOKEN,
        )
        self.architecture: BackendV2 = self._provider.get_backend()
        self.name: str = "iqm-generic"

    def run(self, circuit: QuantumCircuit, shots: int, **kwargs) -> IQMJob:
        return self.architecture.run(circuit, shots=shots, **kwargs)


__all__ = ["IQMProvided"]
