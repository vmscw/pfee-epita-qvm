"""Job data structures shared by the hypervisor, the scheduler, the mapping and the executor.

A job goes through three forms in the hypervisor:
`Job` (validated, queued) -> scheduling decision `(Job, vms)` -> `PlacedJob`
(circuit + physical qubits), and placed jobs run together in a `Batch`.
The `Job` also carries its own state (status, counts or error) for its whole life.

This module holds data only: no validation, policy, mapping or execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from qiskit import QuantumCircuit


class JobState(StrEnum):
    """Life cycle of a job: QUEUED -> RUNNING -> DONE or ERROR (a StrEnum: equal to its name)."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass
class Job:
    """A validated job and its state.

    request: {"category": name} or {"vms": [vm names]}; circuit qubit i is node
             i of the request's graph (category graph or fused graph).
    status:  where the job is in its life cycle.
    counts:  its counts once DONE ({bitstring: int}, bit 0 rightmost), else None.
    error:   the cause once ERROR, else None.
    """

    job_id: str
    request: dict[str, Any]
    shots: int
    circuit: QuantumCircuit
    status: JobState = JobState.QUEUED
    counts: dict[str, int] | None = None
    error: Exception | None = None


Decision = tuple[Job, list[str]]
"""A scheduling decision: a job and the VM ids it runs on."""


@dataclass
class PlacedJob:
    """A job ready to run: its circuit and the physical qubit of each circuit qubit.

    physical_qubits[i] is the physical qubit of circuit qubit i.
    """

    job_id: str
    circuit: QuantumCircuit
    physical_qubits: list[int]
    shots: int


@dataclass
class Batch:
    """Jobs run together in one execution (all with the same shots).

    jobs: the placed jobs, in queue order.
    vms:  vms[i] = the VM ids used by jobs[i] (recorded in `Hypervisor.history`).
    """

    jobs: list[PlacedJob] = field(default_factory=list)
    vms: list[list[str]] = field(default_factory=list)

    @property
    def shots(self) -> int:
        """Shots of the batch (those of its first job); 0 if empty."""
        return self.jobs[0].shots if self.jobs else 0
