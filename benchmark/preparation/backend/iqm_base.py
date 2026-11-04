from abc import ABC
from collections import Counter

from qiskit import transpile
import qiskit.qasm2
from qiskit_scaleway import ScalewayProvider

from benchmark.preparation.backend import Backend


class IQMBase(ABC):
    """Abstract structure for any backend based on an IQM quantum computer.

    Args:
        computer (str): the IQM quantum computer at which to submit jobs
    """

    def __init__(self, computer: str):
        self._provider = ScalewayProvider()
        self._engine = self._provider.get_backend(computer)

    def run(self, circuit: str) -> Counter:
        qiskit_circuit = qiskit.qasm2.loads(circuit)
        job = self._engine.run(qiskit_circuit)
        return job.result().get_counts()


__all__ = ["IQMBase"]
