"""Scheduling policy: which queued jobs run together, and on which VMs.

`Scheduler.schedule` implements HyperQ pass 1 (spatial placement) on VMs:
jobs are tried in queue order, a job that does not fit is skipped and later
jobs may pass it. It only produces decisions `(Job, vms)`.

This module must not know the circuits' content, the physical qubits (see
`ultraq_backend.steps.mapping`), the execution target nor any vendor.
"""

from __future__ import annotations

from ultraq_backend.model.jobs import Decision, Job
from ultraq_backend.model.virtual_topology import VirtualTopology


class Scheduler:
    """HyperQ pass 1: places jobs on the free VMs of a `VirtualTopology`."""

    def __init__(self, virtual_topology: VirtualTopology) -> None:
        self.virtual_topology = virtual_topology

    def place(self, job: Job, free: set[str]) -> list[str] | None:
        """VMs to run `job` on, or None if it must wait.

        Category job: the first free VM of the category (declaration order).
        Fused job: its VMs, only if all of them are free.
        """
        if "category" in job.request:
            for vm in self.virtual_topology.vms_of(job.request["category"]):
                if vm.name in free:
                    return [vm.name]
            return None
        vms = list(job.request["vms"])
        return vms if set(vms) <= free else None

    def schedule(self, queue: list[Job]) -> tuple[list[Decision], list[Job]]:
        """HyperQ pass 1 (spatial), plus one rule: same shots in a batch.

        Jobs are tried in queue order; a job that does not fit (no free VM,
        or shots different from the first placed job) is skipped and later
        jobs may pass it; stops trying once no VM is free.
        Returns (decisions for the next batch, remaining jobs in queue order).
        """
        free = {vm.name for vm in self.virtual_topology.vms}
        decisions: list[Decision] = []
        remaining: list[Job] = []
        for job in queue:
            vms = None
            if free and (not decisions or job.shots == decisions[0][0].shots):
                vms = self.place(job, free)
            if vms is None:
                remaining.append(job)
                continue
            free -= set(vms)
            decisions.append((job, vms))
        return decisions, remaining
