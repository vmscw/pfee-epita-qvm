"""The chip layout: a chip (`ultraq_backend.model.chips.PhysicalChip`) cut into VMs.

Default layout (`ChipLayout.whole_chip`): the whole chip as ONE VM — a single
category "chip" whose graph is the active qubits and active couplers, and a
single VM "chip" of that category. No file needed, valid for any snapshot.

File format (JSON) of a hand-written cut into several VMs:

    {"chip": "<chip name>",                    # a key of `ultraq_backend.model.chips.CHIPS`
     "snapshot": "<timestamp>",                # optional, default "latest"
     "categories": [{"name": name, "qubits": [...], "edges": [[a, b], ...]}],
     "vms": [{"name": name, "category": category name, "connectors": {"<n>": [labels]}}],
     "mapping": {vm_id: {label: physical qubit index of the chip}}}

The chip is built from a cached calibration snapshot (`ultraq_backend.model.chips.load_chip`):
a layout is valid for that snapshot only (a qubit or coupler may be off on
another day). The `basis_gates` of the topology are the chip's native gates.
This module must not know the scheduling, the executor nor any specific
vendor or gate name.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultraq_backend.model.chips import CACHE_ROOT, PhysicalChip, load_chip
from ultraq_backend.model.virtual_topology import VirtualTopology, topology_from_dicts
from ultraq_backend.model.vm import connector_number


@dataclass
class ChipLayout:
    """A chip cut into VMs: the physical chip, the virtual topology and the mapping between them.

    physical_chip:    the physical chip (qubits, couplers, native gates, calibration).
    virtual_topology: categories and VMs, as seen by the scheduler and the users;
                      its `basis_gates` must be the chip's native gates (Qiskit
                      names, without "measure").
    mapping:          {vm_name: {label: physical qubit index}} for every node of every VM.

    Construction checks `virtual_topology` and `mapping` against
    `physical_chip` (see `check`) and raises ValueError.
    """

    physical_chip: PhysicalChip
    virtual_topology: VirtualTopology
    mapping: dict[str, dict[str, int]]

    def __post_init__(self) -> None:
        self.check()

    @classmethod
    def from_dict(cls, data: dict[str, Any], root: str | Path = CACHE_ROOT) -> ChipLayout:
        """Build from the file format (see the module docstring).

        The chip is loaded with `load_chip(data["chip"], data.get("snapshot",
        "latest"), root)`; the topology gets the chip's gates as `basis_gates`. Raises KeyError
        for an unknown chip, FileNotFoundError for a missing snapshot,
        ValueError for an invalid layout.
        """
        chip = load_chip(data["chip"], data.get("snapshot", "latest"), root)
        topology = topology_from_dicts(
            {"basis_gates": _gates(chip), "categories": data["categories"]},
            {"vms": data["vms"]},
        )
        mapping = {vm: {label: int(p) for label, p in m.items()} for vm, m in data["mapping"].items()}
        return cls(physical_chip=chip, virtual_topology=topology, mapping=mapping)

    @classmethod
    def whole_chip(cls, chip: PhysicalChip) -> ChipLayout:
        """The default layout: the whole chip as one category "chip" and one VM "chip".

        Nodes "q0", "q1"... are the active qubits in index order (node i =
        `chip.active_qubits[i]`), edges are the active couplers. Inactive
        qubits are left out, so node indices may differ from physical indices.
        """
        active = chip.active_qubits
        label = {p: f"q{i}" for i, p in enumerate(active)}
        topology = topology_from_dicts(
            {
                "basis_gates": _gates(chip),
                "categories": [
                    {
                        "name": "chip",
                        "qubits": [label[p] for p in active],
                        "edges": [[label[a], label[b]] for a, b in chip.active_couplers],
                    }
                ],
            },
            {"vms": [{"name": "chip", "category": "chip", "connectors": {}}]},
        )
        mapping = {"chip": {label[p]: p for p in active}}
        return cls(physical_chip=chip, virtual_topology=topology, mapping=mapping)

    @classmethod
    def from_file(cls, path: str | Path, root: str | Path = CACHE_ROOT) -> ChipLayout:
        """Load a layout JSON file (see `from_dict`)."""
        return cls.from_dict(json.loads(Path(path).read_text()), root)

    def check(self) -> None:
        """Raise ValueError unless `virtual_topology` and `mapping` are consistent with `physical_chip`.

        - the topology's `basis_gates` are the chip's native gates;
        - no mapping for an unknown VM, every VM has a mapping;
        - every label of every VM is mapped, no unknown label;
        - a physical qubit is never used by two different nodes (a connector
          is the same node in its two VMs, a plain qubit belongs to one VM);
        - a connector maps to the same physical qubit in its two VMs;
        - every physical qubit exists on the chip and is active in its snapshot;
        - every edge of every VM graph (category edges and connector
          attachments) is an active coupler of the chip.
        """
        if self.virtual_topology.basis_gates != _gates(self.physical_chip):
            raise ValueError(
                f"basis gates {self.virtual_topology.basis_gates} differ from chip "
                f"{self.physical_chip.id!r} gates {_gates(self.physical_chip)}"
            )
        unknown = set(self.mapping) - {vm.name for vm in self.virtual_topology.vms}
        if unknown:
            raise ValueError(f"physical mapping for unknown VM(s) {sorted(unknown)}")
        owner: dict[int, str] = {}  # physical qubit -> node name
        connector_qubit: dict[int, int] = {}  # connector number -> physical qubit
        for vm in self.virtual_topology.vms:
            vm_map = self.mapping.get(vm.name)
            if vm_map is None:
                raise ValueError(f"{vm.name}: no mapping")
            graph_labels = {n.label for n in vm.graph.nodes()}
            extra = set(vm_map) - graph_labels
            if extra:
                raise ValueError(f"{vm.name}: physical mapping has unknown labels {sorted(extra)}")
            for node in vm.graph.nodes():
                if node.label not in vm_map:
                    raise ValueError(f"{vm.name}: label {node.label!r} has no physical qubit")
                p = vm_map[node.label]
                if not 0 <= p < self.physical_chip.num_qubits:
                    raise ValueError(
                        f"{vm.name}: {node.label!r} -> physical qubit {p} not on chip "
                        f"{self.physical_chip.id!r} ({self.physical_chip.num_qubits} qubits)"
                    )
                if not self.physical_chip.qubit(p).active:
                    raise ValueError(
                        f"{vm.name}: {node.label!r} -> physical qubit {p} ({self.physical_chip.qubit(p).label}) "
                        f"is inactive on chip {self.physical_chip.id!r} (snapshot {self.physical_chip.snapshot})"
                    )
                if node.kind == "connector":
                    number = connector_number(node.label)
                    name = f"connector {number}"
                    if connector_qubit.setdefault(number, p) != p:
                        raise ValueError(
                            f"connector {number} maps to physical qubits "
                            f"{connector_qubit[number]} and {p}"
                        )
                else:
                    name = f"{vm.name}:{node.label}"
                if owner.setdefault(p, name) != name:
                    raise ValueError(f"physical qubit {p} used by both {owner[p]} and {name}")
            for a, b in vm.graph.edge_list():
                la, lb = vm.graph[a].label, vm.graph[b].label
                pa, pb = vm_map[la], vm_map[lb]
                if not self.physical_chip.graph.has_edge(pa, pb):
                    raise ValueError(
                        f"{vm.name}: edge {la}-{lb} -> physical {pa}-{pb} is not a coupler "
                        f"of chip {self.physical_chip.id!r}"
                    )
                if not self.physical_chip.coupler(pa, pb).active:
                    raise ValueError(
                        f"{vm.name}: edge {la}-{lb} -> coupler {pa}-{pb} is inactive on chip "
                        f"{self.physical_chip.id!r} (snapshot {self.physical_chip.snapshot})"
                    )

    @property
    def num_physical_qubits(self) -> int:
        """Size of the physical register: the chip's number of qubits."""
        return self.physical_chip.num_qubits


def _gates(chip: PhysicalChip) -> list[str]:
    """The chip's native gates in Qiskit names, without "measure" (topology form)."""
    return [g for g in chip.qiskit_basis_gates() if g != "measure"]
