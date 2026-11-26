from collections import Counter
from collections.abc import Sequence
import warnings

from qiskit import transpile
from qiskit.providers import JobV1

from benchmark.config import invoke_config
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

    def duration(self) -> float:
        result = self._job.result()

        print(type(result))
        duration_s = result.metadata.get("time_taken_execute", 0.0)

        if duration_s == 0.0:
            warnings.warn(
                f"duration for job {self.id} is zero. it might be unavailable"
            )

        return duration_s * 1000


class Sequential:
    """Fake scheduler. Runs all circuits separately.

    Typically used to retrieve the performance of each benchmark case when run
    alone on the QPU.

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        config = invoke_config()

        self.name = "sequential"
        self.backend: Backend = backend
        self._num_shots = config.num_shots
        self._seed = config.seed

    def run(self, batch: Batch) -> list[SequentialJob]:
        jobs = []

        for name, circuit in batch:
            circuit = qasm2_to_qiskit(circuit)

            if circuit is None:
                continue

            isa = transpile(
                circuit, self.backend.architecture, seed_transpiler=self._seed
            )
            job = self.backend.run(isa, shots=self._num_shots)

            jobs.append(SequentialJob(job, name, isa.num_qubits))

        return jobs


__all__ = ["Sequential", "SequentialJob"]
