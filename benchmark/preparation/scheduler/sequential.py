from collections import Counter
from collections.abc import Sequence

from qiskit.providers import JobV1

from benchmark.preparation.backend import Backend
from benchmark.preparation.batch import Batch
from benchmark.utils import qasm2_to_qiskit


class SequentialJob:
    """Implementation of a job generated from a sequential "scheduler"."""

    def __init__(self, job: JobV1, circuit: str, num_qubits: int):
        self.id: str
        self.circuits: Sequence[str]
        self.qvms: Sequence[Sequence[int]]

        self._job = job
        self.id = job.job_id()
        self.circuits = [circuit]
        self.qvms = [list(range(num_qubits))]

    def result(self) -> dict[str, Counter]:
        result = self._job.result()
        name = self.circuits[0]
        return {name: result.get_counts()}


class Sequential:
    """Fake scheduler. Runs all circuits separately.

    Typically used to retrieve the performance of each benchmark case when run
    alone on the QPU.

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        self.backend: Backend = backend

    def run(self, batch: Batch) -> list[SequentialJob]:
        jobs = []

        for name, circuit in batch:
            if (job := self.backend.run(circuit)) is None:
                continue

            # temporary hack
            circuit = qasm2_to_qiskit(circuit)
            assert circuit is not None
            num_qubits = circuit.num_qubits

            jobs.append(SequentialJob(job, circuit=name, num_qubits=num_qubits))

        return jobs


__all__ = ["Sequential", "SequentialJob"]
