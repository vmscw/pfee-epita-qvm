"""Executor: build the composite circuit of a batch and run it on a Qiskit backend.

This is the only target-dependent part of ultraq. `Executor.execute` receives
placed jobs (circuit + physical qubits) and returns each job's counts; it must
not know the VMs, the queue nor the scheduling policy. The batch becomes one
circuit (`combine`), run as-is on the physical qubits chosen by ultraq; its
counts are split back per job (`split_counts`).

`Executor` is abstract: subclasses only create the backend (`make_backend`):
`AerExecutor` (`aer.py`), `IQMExecutor` (`iqm.py`).

`execute` blocks until the backend returns (for IQM: queue + execution, polled
over HTTP). The hypervisor calls it outside its lock, so `submit`/`result`
stay usable meanwhile; only one batch is in flight at a time.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

from ultraq_backend.model.jobs import PlacedJob

log = logging.getLogger(__name__)


class Executor(ABC):
    """Runs batches of placed jobs on a Qiskit backend, created by `make_backend`.

    run_options:    extra keyword arguments of `backend.run` (e.g. Aer
                    `{"seed_simulator": 1}` for reproducible simulations).
    result_options: keyword arguments of `job.result()` (e.g. `{"timeout": 600}`).

    `job_ids`: id of the backend job of each executed batch, in order (to get a
    remote job back after a crash, e.g. `backend.retrieve_job(job_id)`).
    """

    def __init__(
        self,
        run_options: dict[str, Any] | None = None,
        result_options: dict[str, Any] | None = None,
    ) -> None:
        self.backend = self.make_backend()
        self.run_options = dict(run_options or {})
        self.result_options = dict(result_options or {})
        self.job_ids: list[str] = []

    @abstractmethod
    def make_backend(self) -> Any:
        """The Qiskit backend of this target (called once, by `__init__`); its
        `run(circuit, shots=...)` must accept the composite circuit as-is (the
        job gates on the physical qubits)."""

    def combine(self, batch: list[PlacedJob]) -> QuantumCircuit:
        """One circuit over the physical qubits 0..max used, with one register
        `job{i}_c` per job; each job circuit is composed on its physical
        qubits (no global barrier, no reset)."""
        num_qubits = 1 + max(q for job in batch for q in job.physical_qubits)
        circuit = QuantumCircuit(QuantumRegister(num_qubits, "q"))
        for i, job in enumerate(batch):
            creg = ClassicalRegister(job.circuit.num_clbits, f"job{i}_c")
            circuit.add_register(creg)
            circuit.compose(job.circuit, qubits=job.physical_qubits, clbits=list(creg), inplace=True)
        return circuit

    def failure_reason(self, job: Any, result: Any) -> str:
        """Why the backend job failed (for the RuntimeError of `execute`)."""
        return str(result.status)

    def execute(self, batch: list[PlacedJob], shots: int) -> list[dict[str, int]]:
        """Run `combine(batch)` `shots` times and return the counts of each
        job, in batch order, split by register name (`split_counts`).

        Counts keys are the job's own bits in Qiskit order (bit 0 rightmost),
        as many characters as the job circuit's clbits, no spaces. A register
        missing from the backend's keys (IQM drops never-measured registers)
        reads as all zeros. Returns [] for an empty batch; raises RuntimeError
        if the backend reports a failed result.
        """
        if not batch:
            return []
        circuit = self.combine(batch)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("composite circuit: %d qubits, %d registers, depth %d, size %d",
                      circuit.num_qubits, len(circuit.cregs), circuit.depth(), circuit.size())
        job = self.backend.run(circuit, shots=shots, **self.run_options)
        job_id = str(job.job_id())
        self.job_ids.append(job_id)
        log.info("batch of %d job(s) submitted as backend job %s", len(batch), job_id)
        start = time.monotonic()
        result = job.result(**self.result_options)
        log.debug("backend job %s done in %.2f s", job_id, time.monotonic() - start)
        if not result.success:
            raise RuntimeError(f"backend job {job_id} failed: {self.failure_reason(job, result)}")
        per_job = split_counts(result.get_counts(), circuit)
        if log.isEnabledFor(logging.DEBUG):
            for placed, counts in zip(batch, per_job, strict=True):
                log.debug("job %s: %d distinct outcome(s), %d shots",
                          placed.job_id[:8], len(counts), sum(counts.values()))
        return per_job


def split_counts(counts: dict[str, int], circuit: QuantumCircuit) -> list[dict[str, int]]:
    """Split the counts of `combine`'s circuit per register `job{i}_c`, in register order.

    Qiskit count keys: one space-separated field per classical register, the
    last register first. Some backends (IQM) leave out the registers that no
    measurement writes: then the fields are those of the measured registers
    only, and the missing registers read as all zeros.
    """
    cregs = list(circuit.cregs)
    measured = {circuit.find_bit(clbit).registers[0][0].name
                for inst in circuit.data if inst.operation.name == "measure" for clbit in inst.clbits}
    per_job: list[dict[str, int]] = [{} for _ in cregs]
    for key, n in counts.items():
        fields = key.split(" ")
        names = [c.name for c in cregs]
        if len(fields) != len(names):
            names = [c.name for c in cregs if c.name in measured]
        values = dict(zip(names[::-1], fields, strict=True))
        for i, creg in enumerate(cregs):
            bits = values.get(creg.name, "0" * creg.size)
            per_job[i][bits] = per_job[i].get(bits, 0) + n
    return per_job
