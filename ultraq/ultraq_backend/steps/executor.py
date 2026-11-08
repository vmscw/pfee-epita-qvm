"""Executor: build the composite circuit of a batch and run it on a Qiskit backend.

This is the only target-dependent part of ultraq. `Executor.execute` receives
placed jobs (circuit + physical qubits) and returns each job's counts; it must
not know the VMs, the queue nor the scheduling policy.
"""

from __future__ import annotations

from typing import Any

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit_aer import AerSimulator

from ultraq_backend.model.jobs import PlacedJob


class Executor:
    """Runs batches of placed jobs on a Qiskit backend (Aer by default).

    backend: a Qiskit backend whose `run(circuit, shots=...)` accepts the
             composite circuit as-is (the job gates on the physical qubits);
             default `AerSimulator()`.
    seed:    if not None, passed as `seed_simulator` to `backend.run`
             (reproducible simulations on Aer).
    """

    def __init__(self, backend: Any = None, seed: int | None = None) -> None:
        self.backend = backend if backend is not None else AerSimulator()
        self.seed = seed

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

    def execute(self, batch: list[PlacedJob], shots: int) -> list[dict[str, int]]:
        """Run `combine(batch)` `shots` times and return the counts of each
        job, in batch order, split by register name.

        Counts keys are the job's own bits in Qiskit order (bit 0 rightmost),
        as many characters as the job circuit's clbits, no spaces.
        """
        if not batch:
            return []
        circuit = self.combine(batch)
        options = {} if self.seed is None else {"seed_simulator": self.seed}
        counts = self.backend.run(circuit, shots=shots, **options).result().get_counts()
        # Qiskit count keys: one space-separated field per classical register,
        # the last register first.
        names = [creg.name for creg in circuit.cregs][::-1]
        per_job: list[dict[str, int]] = [{} for _ in batch]
        for key, n in counts.items():
            fields = dict(zip(names, key.split(" "), strict=True))
            for i, job_counts in enumerate(per_job):
                bits = fields[f"job{i}_c"]
                job_counts[bits] = job_counts.get(bits, 0) + n
        return per_job
