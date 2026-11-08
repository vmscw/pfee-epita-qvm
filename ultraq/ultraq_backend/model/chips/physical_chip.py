"""Vendor-agnostic chip model: `PhysicalChip`, `Qubit`, `Coupler`, `RawMetric`.

A chip is a coupling graph whose node payloads are `Qubit` objects and edge
payloads `Coupler` objects; each carries its calibration data. Chip-wide data
(not tied to a qubit or a coupler) is on the `PhysicalChip` itself.

Vendor subclasses (e.g. `ultraq_backend.model.chips.iqm.IQMGarnet`) know how to fetch and
read their calibration data and build a `PhysicalChip`; this module must not know any
vendor, data format or API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rustworkx as rx
from qiskit.circuit.library import get_standard_gate_name_mapping
from qiskit.transpiler import (
    CouplingMap,
    InstructionProperties,
    QubitProperties,
    Target,
)


@dataclass
class RawMetric:
    """One raw calibration value (measured metric or setting), kept as the vendor gave it.

    name:   the vendor's identifier (e.g. IQM "characterization.model.QB5.t1_time").
    value:  number, bool, str or structured data (dict), unchanged.
    unit:   unit as given by the vendor ("" if none).
    source: which part of the vendor data it comes from (e.g. "metrics").
    extra:  every other vendor-specific field, unchanged (e.g. IQM "uncertainty",
            "invalid", "observation_id", timestamps).
    """

    name: str
    value: Any
    unit: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Qubit:
    """A physical qubit (node payload of `PhysicalChip.graph`).

    active: usable in this snapshot (inactive = present on the chip but off).
    t1, t2: coherence times in seconds (T2 = Ramsey), None if unknown.
    gate_fidelity: {Qiskit gate name: fidelity} on this qubit (e.g. "r", "measure").
    raw_metrics: every raw value attached to this qubit.
    """

    label: str
    active: bool = True
    t1: float | None = None
    t2: float | None = None
    gate_fidelity: dict[str, float] = field(default_factory=dict)
    raw_metrics: list[RawMetric] = field(default_factory=list)


@dataclass
class Coupler:
    """A physical coupler between two qubits (edge payload of `PhysicalChip.graph`).

    active: its 2-qubit gates are usable in this snapshot.
    gate_fidelity: {Qiskit gate name: fidelity} on this pair (e.g. "cz").
    raw_metrics: every raw value attached to this pair.
    """

    active: bool = True
    gate_fidelity: dict[str, float] = field(default_factory=dict)
    raw_metrics: list[RawMetric] = field(default_factory=list)


@dataclass
class PhysicalChip:
    """A chip in a given calibration snapshot.

    graph: node i = physical qubit i (`Qubit`), edge = physical coupler
        (`Coupler`, stored a -> b; the direction matters only for a gate not
        in `symmetric_gates`). Inactive qubits and couplers stay in the graph
        so that indices are stable from one snapshot to the next.
    native_gates: {vendor gate name: Qiskit gate name}.
    symmetric_gates: vendor names of the 2-qubit gates usable both ways.
    snapshot: identifier of the calibration snapshot (None if none).
    raw_metrics: raw values tied to no single qubit or coupler.

    Only what every vendor has belongs here; a chip subclass adds its own
    vendor-specific fields, which generic code never reads.
    """

    id: str
    name: str
    vendor: str
    native_gates: dict[str, str]
    symmetric_gates: set[str]
    graph: rx.PyGraph
    snapshot: str | None = None
    raw_metrics: list[RawMetric] = field(default_factory=list)

    # ------------------------------------------------------------ chip class contract

    @classmethod
    def fetch(cls, *args: Any, **kwargs: Any) -> PhysicalChip:
        """Fetch the current calibration from the vendor, cache it and build the chip.

        Every chip class registered in `CHIPS` overrides it (network access).
        """
        raise NotImplementedError(f"{cls.__name__} does not implement fetch()")

    @classmethod
    def load(cls, snapshot: str = "latest", root: str | Path | None = None) -> PhysicalChip:
        """Build the chip from a cached snapshot ("latest" or a timestamp), without network.

        Every chip class registered in `CHIPS` overrides it and defines its own
        default cache `root`; `load_chip` relies on it.
        """
        raise NotImplementedError(f"{cls.__name__} does not implement load()")

    # ------------------------------------------------------------ structure

    @property
    def num_qubits(self) -> int:
        """Number of physical qubits (graph nodes, active or not)."""
        return self.graph.num_nodes()

    @property
    def num_couplers(self) -> int:
        """Number of physical couplers (graph edges, active or not)."""
        return self.graph.num_edges()

    def qubit(self, i: int) -> Qubit:
        """The `Qubit` at physical index `i`."""
        return self.graph[i]

    def coupler(self, a: int, b: int) -> Coupler:
        """The `Coupler` between physical qubits `a` and `b` (either order); KeyError if none."""
        try:
            return self.graph.get_edge_data(a, b)
        except rx.NoEdgeBetweenNodes:
            raise KeyError(f"chip {self.id!r}: no coupler between qubits {a} and {b}") from None

    def index(self, label: str) -> int:
        """Physical index of the qubit labelled `label`; KeyError if unknown."""
        for i in self.graph.node_indices():
            if self.graph[i].label == label:
                return i
        raise KeyError(f"chip {self.id!r}: unknown qubit {label!r}")

    @property
    def active_qubits(self) -> list[int]:
        """Indices of the active qubits, ascending."""
        return [i for i in self.graph.node_indices() if self.graph[i].active]

    @property
    def active_couplers(self) -> list[tuple[int, int]]:
        """Active couplers (a, b) as stored, both qubits active."""
        active = set(self.active_qubits)
        return [
            (a, b)
            for a, b, c in self.graph.weighted_edge_list()
            if c.active and a in active and b in active
        ]

    # ------------------------------------------------------------ Qiskit view

    def qiskit_basis_gates(self) -> list[str]:
        """Native gates translated to Qiskit names, plus "measure".

        Raises ValueError for a Qiskit name that is not a standard Qiskit gate.
        """
        names = list(self.native_gates.values())
        standard = get_standard_gate_name_mapping()
        not_standard = [n for n in names if n not in standard]
        if not_standard:
            raise ValueError(f"chip {self.id!r}: not standard Qiskit gate(s): {not_standard}")
        return names + ["measure"]

    def _two_qubit_gates(self) -> list[str]:
        """Vendor names of the 2-qubit native gates."""
        standard = get_standard_gate_name_mapping()
        return [v for v, q in self.native_gates.items() if standard[q].num_qubits == 2]

    def coupling_map(self) -> CouplingMap:
        """Active couplers; both directions if every 2-qubit gate is symmetric, else a -> b only.

        Inactive qubits appear in no pair. The map has `num_qubits` qubits.
        """
        edges = [list(e) for e in self.active_couplers]
        if all(g in self.symmetric_gates for g in self._two_qubit_gates()):
            edges += [[b, a] for a, b in edges]
        cmap = CouplingMap(edges)
        for q in range(cmap.size(), self.num_qubits):
            cmap.add_physical_qubit(q)
        return cmap

    def target(self) -> Target:
        """Qiskit Target of the active part of the chip, with the calibration errors.

        1-qubit gates and measure on every active qubit, 2-qubit gates on the
        `coupling_map()` pairs. Each instruction gets `error = 1 - fidelity`
        when the fidelity is known; qubit properties carry T1 and T2.
        """
        standard = get_standard_gate_name_mapping()
        qubits = [self.graph[i] for i in range(self.num_qubits)]
        target = Target(
            num_qubits=self.num_qubits,
            qubit_properties=[QubitProperties(t1=q.t1, t2=q.t2) for q in qubits],
        )

        def props(fidelities: dict[str, float], name: str) -> InstructionProperties:
            f = fidelities.get(name)
            return InstructionProperties(error=None if f is None else 1.0 - f)

        pairs = [tuple(e) for e in self.coupling_map().get_edges()]
        for name in self.qiskit_basis_gates():
            gate = standard[name]
            if gate.num_qubits == 1:
                target.add_instruction(
                    gate, {(i,): props(qubits[i].gate_fidelity, name) for i in self.active_qubits}
                )
            elif gate.num_qubits == 2:
                target.add_instruction(
                    gate, {(a, b): props(self.coupler(a, b).gate_fidelity, name) for a, b in pairs}
                )
            else:
                raise ValueError(f"chip {self.id!r}: unsupported {gate.num_qubits}-qubit gate {name!r}")
        return target
