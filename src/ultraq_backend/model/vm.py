"""The bricks of the virtual side: `Node`, `Category` (a VM shape), `VM` (an instance of a category).

A *category* is a VM shape: an undirected graph of plain qubits ("q0", "q1"...).
A *VM* belongs to a category and adds its own *connector* nodes "c<n>", where
<n> is a number global to the chip. A connector number appears in exactly two
VMs: it is one physical qubit shared by them, usable only when both VMs are
fused in one job (see `ultraq_backend.model.virtual_topology.fuse`).

This module must not know the topology as a whole (`ultraq_backend.model.virtual_topology`),
physical qubits, vendors, the scheduling nor the execution target. All graphs
are undirected `rustworkx.PyGraph` whose node payloads are `Node` and whose
indices are compact (0..n-1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import rustworkx as rx


@dataclass(frozen=True)
class Node:
    """Payload of every graph node.

    kind:  "qubit" (plain qubit) or "connector" (qubit shared with another VM;
           only found in VM graphs).
    label: name unique inside its graph: "q3" in a category, "c7" for
           connector 7 in a VM, "vm1:q3" or "c7" in a fused graph.
    """

    kind: Literal["qubit", "connector"]
    label: str


def connector_number(label: str) -> int:
    """Global number of a connector from its label: "c7" -> 7.

    Raises ValueError if `label` is not of the form "c<n>".
    """
    if not (label.startswith("c") and label[1:].isdigit()):
        raise ValueError(f"not a connector label: {label!r}")
    return int(label[1:])


def labels(graph: rx.PyGraph) -> dict[str, int]:
    """{label: node index} of a graph of `Node` payloads."""
    return {graph[i].label: i for i in graph.node_indices()}


@dataclass
class Category:
    """A VM shape, the general type of a VM: a name and an undirected graph of plain qubit nodes only.

    All the VMs of a category share its graph (same nodes, same indices), so a
    circuit compiled once for the category runs on any of them.
    """

    name: str
    graph: rx.PyGraph

    @property
    def num_qubits(self) -> int:
        """Number of qubits of the category (graph nodes)."""
        return self.graph.num_nodes()


@dataclass
class VM:
    """A VM: one instance of a category, i.e. a copy of its category graph followed by its connector nodes.

    category: the `Category` object it is an instance of.
    Node i < category.num_qubits is category qubit i; connector nodes come
    after, sorted by connector number, so the graph only depends on the
    category and the connectors (rebuilding it always gives the same graph,
    node for node).
    """

    name: str
    category: Category
    graph: rx.PyGraph

    @classmethod
    def build(cls, vm_id: str, category: Category, connectors: dict[int, list[str]]) -> VM:
        """Build a VM from `connectors` = {number: [category labels it is linked to]}.

        Raises ValueError if a connector is attached to nothing or to an
        unknown category label.
        """
        graph = category.graph.copy()
        by_label = labels(category.graph)
        for number in sorted(connectors):
            attached = connectors[number]
            if not attached:
                raise ValueError(f"{vm_id}: connector {number} attached to nothing")
            c = graph.add_node(Node("connector", f"c{number}"))
            for label in attached:
                if label not in by_label:
                    raise ValueError(
                        f"{vm_id}: connector {number} attached to unknown label {label!r}"
                    )
                graph.add_edge(c, by_label[label], None)
        return cls(vm_id, category, graph)

    def connectors(self) -> dict[int, list[str]]:
        """{number: sorted attached qubit labels}, by increasing number."""
        out = {}
        for i in self.graph.node_indices():
            node = self.graph[i]
            if node.kind == "connector":
                attached = sorted(self.graph[j].label for j in self.graph.neighbors(i))
                out[connector_number(node.label)] = attached
        return dict(sorted(out.items()))
