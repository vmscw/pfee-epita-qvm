"""`UltraqProvider`: the virtual Qiskit backends of a `Hypervisor`.

One `CategoryBackend` per category, and a `FusedBackend` for any connected
group of VMs (`get_backend(vms=[...])`, helped by `fusion_candidates`).

This module must not know physical qubits, the scheduling policy, the
execution target nor any vendor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ultraq_qiskit_connector.backend import CategoryBackend, FusedBackend

if TYPE_CHECKING:
    from ultraq_backend.hypervisor import Hypervisor


class UltraqProvider:
    """Provider of the virtual backends of one hypervisor."""

    def __init__(self, hypervisor: Hypervisor) -> None:
        self.hypervisor = hypervisor

    def backends(self, min_qubits: int | None = None) -> list[CategoryBackend]:
        """One backend per category with at least `min_qubits` qubits, smallest first."""
        cats = sorted(self.hypervisor.virtual_topology.categories, key=lambda c: c.num_qubits)
        return [
            CategoryBackend(c.name, self.hypervisor, self)
            for c in cats
            if min_qubits is None or c.num_qubits >= min_qubits
        ]

    def get_backend(
        self, name: str | None = None, *, vms: list[str] | None = None
    ) -> CategoryBackend | FusedBackend:
        """Backend of category `name` (e.g. "S4" or "ultraq_S4"), or of the
        fused VM group `vms` (e.g. ["vm3", "vm4"]; any order, the backend
        keeps them in declaration order). Give exactly one of them.

        Raises ValueError for an unknown category or an invalid group
        (unknown, duplicated or non-connected VMs).
        """
        if (name is None) == (vms is None):
            raise ValueError("give either a category name or vms=[...], not both")
        if vms is not None:
            return FusedBackend(list(vms), self.hypervisor, self)
        return CategoryBackend(name.removeprefix("ultraq_"), self.hypervisor, self)

    def fusion_candidates(self, num_qubits: int) -> list[list[str]]:
        """Connected VM groups whose fusion has >= `num_qubits` qubits,
        smallest first. A help to choose `get_backend(vms=...)`, not a choice."""
        return self.hypervisor.virtual_topology.fusion_candidates(num_qubits)
