from collections import Counter
from collections.abc import Collection, Sequence

from qiskit.providers import JobV1

from benchmark.preparation.backend import Backend
from benchmark.preparation.batch import Batch


class SequentialJob:
    """Implementation of a job generated from a sequential "scheduler"."""

    def __init__(self, job: JobV1, circuit: str):
        self.id: str
        self.circuits: Sequence[str]
        self.qvms: Sequence[Sequence[int]]

        self._job = job
        self.id = job.job_id()
        self.circuits = [circuit]
        self.qvms = []

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

            jobs.append(SequentialJob(job, circuit=name))

        return jobs


__all__ = ["Sequential", "SequentialJob"]
