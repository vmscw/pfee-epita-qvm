from benchmark.utils import qasm2_to_qiskit
from abc import ABC
from collections import Counter

from qiskit import transpile
import qiskit.qasm2
from qiskit_scaleway import ScalewayProvider

from benchmark.config import invoke_config


class IQMBase(ABC):
    """Abstract structure for any backend based on an IQM quantum computer.

    Args:
        computer (str): the IQM quantum computer at which to submit jobs
    """

    def __init__(self, computer: str):
        config = invoke_config()

        self._num_shots = config.num_shots
        self._provider = ScalewayProvider()
        self._engine = self._provider.get_backend(computer)

    def run(self, circuit: str) -> Counter:
        qiskit_circuit = qasm2_to_qiskit(circuit)

        if qiskit_circuit is None:
            return Counter()

        job = self._engine.run(qiskit_circuit, shots=self._num_shots)
        return job.result().get_counts()


__all__ = ["IQMBase"]
