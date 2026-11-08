"""Mapping: turn scheduling decisions into placed jobs on physical qubits.

One single translation path: whatever the request, a job placed on VMs `vms`
runs on `fuse(topology, vms)` (a category job placed on VM v is treated as
`fuse(topology, [v])`, which has the category's graph), and the fusion origins
give the physical qubits through the layout `mapping` table. The circuit
itself is not modified.

This module must not know the scheduling policy nor the execution target.
"""

from __future__ import annotations

from ultraq_backend.model.chip_layout import ChipLayout
from ultraq_backend.model.jobs import Batch, Decision, PlacedJob
from ultraq_backend.model.virtual_topology import fuse


class Mapper:
    """Translates VMs to physical qubits on a `ChipLayout`."""

    def __init__(self, chip_layout: ChipLayout) -> None:
        self.chip_layout = chip_layout

    def physical_qubits(self, vms: list[str]) -> list[int]:
        """Physical qubit of each node of `fuse(topology, vms)` (= circuit qubit)."""
        out = []
        for i, origins in enumerate(fuse(self.chip_layout.virtual_topology, vms).origins):
            qubits = {self.chip_layout.mapping[vm][label] for vm, label in origins}
            # Merged connector: both VMs must agree (guaranteed by ChipLayout.check).
            assert len(qubits) == 1, f"node {i}: origins {origins} map to {sorted(qubits)}"
            out.append(qubits.pop())
        return out

    def map(self, decisions: list[Decision]) -> Batch:
        """The batch of placed jobs for these decisions (same order)."""
        batch = Batch()
        for job, vms in decisions:
            batch.jobs.append(PlacedJob(job.job_id, job.circuit, self.physical_qubits(vms), job.shots))
            batch.vms.append(list(vms))
        return batch
