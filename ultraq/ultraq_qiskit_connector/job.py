"""`UltraqJob`: a Qiskit job (JobV1) for one circuit queued in a `Hypervisor`.

The job maps the hypervisor state (a `JobState`, compared as a plain string)
to Qiskit's `JobStatus` and turns the job counts
into a standard `qiskit.result.Result` (so `get_counts()` works as with Aer,
and `memory=True` for the primitives).

This module must not know the scheduling, the VMs used or any physical
qubit: it only sees a job id, a status string and counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qiskit.providers import JobError, JobStatus, JobV1
from qiskit.result import Result

if TYPE_CHECKING:
    from ultraq_backend.hypervisor import Hypervisor

_STATUS = {
    "QUEUED": JobStatus.QUEUED,
    "RUNNING": JobStatus.RUNNING,
    "DONE": JobStatus.DONE,
    "ERROR": JobStatus.ERROR,
}


class UltraqJob(JobV1):
    """One circuit queued in a hypervisor (created by `backend.run`).

    `header` describes the classical bits of the circuit ({"name",
    "creg_sizes", "memory_slots"}), used to format the counts; `memory` asks
    for per-shot results (rebuilt from the counts, so the shot order is not
    the measurement order).
    """

    def __init__(
        self,
        backend: Any,
        job_id: str,
        hypervisor: Hypervisor,
        header: dict[str, Any],
        shots: int,
        memory: bool = False,
    ) -> None:
        super().__init__(backend, job_id)
        self._hypervisor = hypervisor
        self._header = header
        self._shots = shots
        self._memory = memory
        self._result: Result | None = None

    def submit(self) -> None:
        """No-op: `backend.run` already queued the job (required by JobV1)."""

    def status(self) -> JobStatus:
        """Current status of the job, as a `qiskit.providers.JobStatus`."""
        return _STATUS[self._hypervisor.status(self.job_id())]

    def result(self) -> Result:
        """The job result (cached). Raises JobError if the job failed.

        Waits until the hypervisor's background thread has run the job.
        """
        if self._result is None:
            try:
                counts = self._hypervisor.result(self.job_id())
            except RuntimeError as exc:
                raise JobError(str(exc)) from exc
            self._result = self._build_result(counts)
        return self._result

    def _build_result(self, counts: dict[str, int]) -> Result:
        """Standard Qiskit Result from counts (bitstrings, bit 0 rightmost)."""
        hex_counts = {hex(int(bits, 2)): n for bits, n in counts.items()}
        data: dict[str, Any] = {"counts": hex_counts}
        if self._memory:
            data["memory"] = [h for h, n in hex_counts.items() for _ in range(n)]
        return Result.from_dict(
            {
                "backend_name": self._backend.name,
                "backend_version": self._backend.backend_version,
                "job_id": self.job_id(),
                "success": True,
                "results": [
                    {
                        "shots": self._shots,
                        "success": True,
                        "data": data,
                        "header": dict(self._header),
                    }
                ],
            }
        )
