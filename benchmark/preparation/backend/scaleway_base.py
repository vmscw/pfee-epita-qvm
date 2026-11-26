from abc import ABC

from qiskit import QuantumCircuit
from qiskit.providers import BackendV2
from qiskit_scaleway import ScalewayProvider
from qiskit_scaleway.backends import BaseBackend, BaseJob

from benchmark.config import invoke_config, invoke_auth_config
from benchmark.utils import qasm2_to_qiskit, SkippedJob


class ScalewayProvided(ABC):
    """Abstract structure for any backend provided by Scaleway QaaS.

    Args:
        backend (str): the backend to pull from the provider
    """

    def __init__(self, backend: str):
        auth_config = invoke_auth_config()

        self._provider = ScalewayProvider(
            project_id=auth_config.SCW_PROJECT_ID,
            secret_key=auth_config.SCW_SECRET_KEY,
        )

        self.architecture: BackendV2 = self._provider.get_backend(backend)
        self.name = "scaleway_provided"
        self.num_qubits = self.architecture.num_qubits

    def run(
        self,
        circuit: QuantumCircuit,
        shots: int,
        **kwargs,
    ) -> BaseJob | SkippedJob:
        return self.architecture.run(circuit, shots=shots, **kwargs)


__all__ = ["ScalewayProvided"]
