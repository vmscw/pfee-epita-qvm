from abc import ABC

from qiskit_scaleway import ScalewayProvider
from qiskit_scaleway.backends import BaseBackend, BaseJob

from benchmark.config import invoke_config
from benchmark.utils import qasm2_to_qiskit


class ScalewayProvided(ABC):
    """Abstract structure for any backend provided by Scaleway QaaS.

    Args:
        backend (str): the backend to pull from the provider
    """

    def __init__(self, backend: str):
        config = invoke_config()

        self._num_shots = config.num_shots
        self._provider = ScalewayProvider()
        self._engine: BaseBackend = self._provider.get_backend(backend)

        self.name = "scaleway_provided"
        self.num_qubits = self._engine.num_qubits

    def run(self, circuit: str) -> BaseJob | None:
        qiskit_circuit = qasm2_to_qiskit(circuit)

        if qiskit_circuit is None:
            return None

        return self._engine.run(qiskit_circuit, shots=self._num_shots)


__all__ = ["ScalewayProvided"]
