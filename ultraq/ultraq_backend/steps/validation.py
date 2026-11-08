"""Validation step: accept or reject a circuit before it is queued.

A circuit must run as-is on the graph it was compiled for (a category graph or
a fusion of VMs). This module must not know physical qubits, the scheduling
nor the execution target.
"""

from __future__ import annotations

import rustworkx as rx
from qiskit import QuantumCircuit


def check_circuit(circuit: QuantumCircuit, graph: rx.PyGraph, basis_gates: list[str]) -> None:
    """Raise ValueError unless `circuit` can run as-is on `graph`.

    Checks: as many qubits as graph nodes; only `basis_gates`, "measure" and
    "barrier"; 2-qubit gates on graph edges only; no gate on 3+ qubits
    (barriers excepted); at least one measurement.
    """
    if circuit.num_qubits != graph.num_nodes():
        raise ValueError(
            f"circuit has {circuit.num_qubits} qubits, graph has {graph.num_nodes()}"
        )
    allowed = set(basis_gates) | {"measure", "barrier"}
    edges = {tuple(sorted(e)) for e in graph.edge_list()}
    measured = False
    for inst in circuit.data:
        name = inst.operation.name
        if name not in allowed:
            raise ValueError(f"non-native gate {name!r} (native: {sorted(basis_gates)})")
        if name == "barrier":
            continue
        measured |= name == "measure"
        qubits = tuple(sorted(circuit.find_bit(q).index for q in inst.qubits))
        if len(qubits) > 2:
            raise ValueError(f"gate {name!r} on {len(qubits)} qubits {qubits}")
        if len(qubits) == 2 and qubits not in edges:
            raise ValueError(f"gate {name!r} on non-edge {qubits}")
    if not measured:
        raise ValueError("circuit measures nothing")
