from typing import Any

from qiskit.providers import JobStatus, JobV1
from qiskit.result import Result


class SkippedJob(JobV1):
    """A placeholder job for circuits that can't be run (e.g., too large).

    Returns an empty Result with zero shots, matching Qiskit's behavior for
    circuits with no measurements. Callers should check if `get_counts()`
    returns `{}` to detect skipped jobs.

    Attributes:
        backend: The backend that couldn't run the circuit.
        reason: A human-readable explanation of why the job was skipped.
    """

    def __init__(self, backend: Any, job_id: str | None = None, reason: str | None = None) -> None:
        super().__init__(backend, job_id or f"skipped_{id(backend)}")
        self._status = JobStatus.DONE
        self._reason = reason or "Circuit skipped by backend: cannot run this circuit"
        self.metadata = {}

    def status(self) -> JobStatus:
        """Return DONE status immediately."""
        return self._status

    def submit(self) -> None:
        """No-op: the job is already \"submitted\" (it was skipped)."""
        pass

    def result(self, timeout: float | None = None) -> Result:
        """Return an empty Result with zero shots.

        Returns a valid Result object with no measurement data (matching Qiskit's
        behavior for circuits with no measurements). The `success` field is True,
        but `get_counts()` will return `{}`.

        Callers can distinguish skipped jobs by checking if the result has empty
        counts or inspecting the job_id prefix ("skipped_").

        Args:
            timeout (float | None): the result retrieval timeout (ignored).

        Returns:
            Result: An empty Result with no measurement data.
        """
        backend_name = getattr(self.backend, 'name', str(type(self.backend)))
        return Result.from_dict({
            "backend_name": backend_name,
            "backend_version": "0.0.0",
            "job_id": self.job_id(),
            "success": True,
            "results": [],
        })

    def cancel(self) -> bool:
        """Return False as skipped jobs cannot be cancelled."""
        return False


__all__ = ["SkippedJob"]
