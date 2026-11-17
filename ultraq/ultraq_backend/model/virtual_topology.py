"""The virtual side of a chip as a whole: `VirtualTopology` (categories + VMs),
fusion of VMs, loading from a layout file and the Qiskit `target` of a VM graph.

The bricks (`Node`, `Category`, `VM`) are in `ultraq_backend.model.vm`. A connector
number appears in exactly two VMs: it is one physical qubit shared by them,
usable only when both VMs are fused in one job (see `fuse`).

`topology_from_dicts` builds a validated `VirtualTopology` from the "categories"
and "vms" parts of a chip layout file. `target` gives the Qiskit Target to
transpile on a graph (`ultraq_backend.steps.validation.check_circuit` checks a circuit
against it).

This module must not know physical qubits, vendors (gate names are already
Qiskit names), the scheduling nor the execution target. All graphs are
undirected `rustworkx.PyGraph` whose node payloads are `Node` and whose
indices are compact (0..n-1): circuit qubit i is node i.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import rustworkx as rx
from qiskit.transpiler import CouplingMap, Target

from ultraq_backend.model.vm import VM, Category, Node, connector_number, labels

Origin = tuple[str, str]
"""(vm_id, label): a node of a VM graph."""


@dataclass
class VirtualTopology:
    """The VM topology of a chip: basis gates, categories and VMs.

    basis_gates:  Qiskit gate names (e.g. ["r", "cz"]), the chip's native gates
                  translated by `PhysicalChip.qiskit_basis_gates`; never vendor names.
    categories:   the categories (general VM types), in declaration order.
    vms:          the VMs (instances of the categories), in declaration order
                  (= placement order); may be empty. Each VM points to its
                  `Category`.
    """

    basis_gates: list[str]
    categories: list[Category]
    vms: list[VM] = field(default_factory=list)

    def category(self, name: str) -> Category:
        """The category called `name`; KeyError (listing the names) if unknown."""
        for cat in self.categories:
            if cat.name == name:
                return cat
        raise KeyError(f"unknown category {name!r} (available: {sorted(c.name for c in self.categories)})")

    def vm(self, name: str) -> VM:
        """The VM called `name`; KeyError (listing the names) if unknown."""
        for vm in self.vms:
            if vm.name == name:
                return vm
        raise KeyError(f"unknown VM {name!r} (available: {[v.name for v in self.vms]})")

    def vms_of(self, category: str) -> list[VM]:
        """VMs of the category called `category`, in declaration order."""
        return [vm for vm in self.vms if vm.category.name == category]

    def canonical_vms(self, vms: list[str]) -> list[str]:
        """The VM group `vms` sorted in declaration order: the canonical order
        of a fused job, so that the order the user gives never matters (see
        `fuse`). Unknown names are kept at the end (`fuse` rejects them)."""
        rank = {vm.name: i for i, vm in enumerate(self.vms)}
        return sorted(vms, key=lambda v: rank.get(v, len(rank)))

    def graph(self, *, category: str | None = None, vms: list[str] | None = None) -> rx.PyGraph:
        """Graph a circuit must be compiled on: the graph of category `category`,
        or `fuse(self, vms).graph`. Give exactly one of `category` and `vms`.

        Raises ValueError for an unknown category or an invalid VM group
        (unknown, duplicated or non-connected VMs).
        """
        if (category is None) == (vms is None):
            raise ValueError("give either category=... or vms=[...], not both")
        if category is not None:
            names = [c.name for c in self.categories]
            if category not in names:
                raise ValueError(f"unknown category {category!r} (available: {sorted(names)})")
            return self.category(category).graph
        try:
            return fuse(self, list(vms)).graph
        except ValueError as exc:
            raise ValueError(f"cannot fuse {list(vms)}: {exc}") from exc

    def target(self, *, category: str | None = None, vms: list[str] | None = None) -> Target:
        """Qiskit Target to compile on: `basis_gates` on the nodes of
        `graph(category=..., vms=...)`, 2-qubit gates on its edges. Same
        arguments and errors as `graph`."""
        return target(self.graph(category=category, vms=vms), self.basis_gates)

    def fusion_candidates(self, num_qubits: int) -> list[list[str]]:
        """Connected VM groups whose fusion has >= `num_qubits` qubits, smallest
        first (see the module function `fusion_candidates`)."""
        return fusion_candidates(self, num_qubits)

    def interconnect(self) -> rx.PyGraph:
        """VM adjacency, computed on demand (never stored nor published).

        Node payload = VM name (in `vms` order); one edge per shared connector,
        whose payload is the connector number (a multigraph: two VMs may share
        several connectors).
        """
        graph = rx.PyGraph()
        index = {vm.name: graph.add_node(vm.name) for vm in self.vms}
        owners: dict[int, list[str]] = {}
        for vm in self.vms:
            for number in vm.connectors():
                owners.setdefault(number, []).append(vm.name)
        for number, vm_ids in sorted(owners.items()):
            if len(vm_ids) == 2:
                graph.add_edge(index[vm_ids[0]], index[vm_ids[1]], number)
        return graph

    def validate(self) -> None:
        """Raise ValueError unless the model invariants hold.

        - categories: unique names; graphs with qubit nodes only, unique
          labels, compact indices;
        - VMs: unique names;
        - each VM: its category is one of `categories`, unique labels,
          connectors attached to category qubits only;
        - each connector number is in exactly two VMs.
        """
        names = [cat.name for cat in self.categories]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate category name(s) {duplicates}")
        for cat in self.categories:
            _check_graph(f"category {cat.name}", cat.graph)
            if any(n.kind != "qubit" for n in cat.graph.nodes()):
                raise ValueError(f"category {cat.name}: only qubit nodes allowed")
        vm_names = [vm.name for vm in self.vms]
        duplicates = sorted({n for n in vm_names if vm_names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate VM name(s) {duplicates}")
        owners: dict[int, list[str]] = {}
        for vm in self.vms:
            if not any(vm.category is cat for cat in self.categories):
                raise ValueError(f"{vm.name}: category {vm.category.name!r} is not in this topology")
            _check_graph(vm.name, vm.graph)
            cat_labels = {n.label for n in vm.category.graph.nodes()}
            for number, attached in vm.connectors().items():
                if not attached or not set(attached) <= cat_labels:
                    raise ValueError(
                        f"{vm.name}: connector {number} must attach to category qubits only"
                    )
                owners.setdefault(number, []).append(vm.name)
        for number, vm_ids in sorted(owners.items()):
            if len(vm_ids) != 2:
                raise ValueError(
                    f"connector {number} is in {len(vm_ids)} VM(s) {vm_ids}, expected 2"
                )


def _check_graph(name: str, graph: rx.PyGraph) -> None:
    if list(graph.node_indices()) != list(range(graph.num_nodes())):
        raise ValueError(f"{name}: node indices must be 0..n-1")
    if len(labels(graph)) != graph.num_nodes():
        raise ValueError(f"{name}: duplicate labels")


# ---------------------------------------------------------------- fusion


@dataclass
class FusedGraph:
    """Result of `fuse`.

    graph:   compact graph of qubit nodes only; circuit qubit i = node i.
    origins: origins[i] = the VM nodes behind node i: [(vm_id, label)], or two
             entries [(vm_a, "c7"), (vm_b, "c7")] for a merged connector. Used by
             the mapping (nodes -> physical qubits).
    """

    graph: rx.PyGraph
    origins: list[list[Origin]]

    @property
    def num_qubits(self) -> int:
        """Number of qubits of the fused graph (graph nodes)."""
        return self.graph.num_nodes()


def fuse(topology: VirtualTopology, vm_ids: list[str]) -> FusedGraph:
    """Merge the graphs of `vm_ids` into one graph to compile on.

    - plain qubits become nodes "vm:label";
    - a connector shared by two fused VMs becomes one qubit node "c<n>",
      linked to the qubits of both sides;
    - connectors to VMs outside the group are dropped.

    The group is taken in declaration order (`topology.canonical_vms`), so
    the order of `vm_ids` does not matter: `fuse(t, ["vm4", "vm1"])` ==
    `fuse(t, ["vm1", "vm4"])`. `fuse(topology, [vm])` has the same nodes
    order and edges as the VM's category. Raises ValueError for an empty, duplicated, unknown or
    non-connected (in `topology.interconnect()`) group.
    """
    vm_ids = list(vm_ids)
    if not vm_ids or len(set(vm_ids)) != len(vm_ids):
        raise ValueError(f"need distinct VM ids, got {vm_ids}")
    known = {vm.name for vm in topology.vms}
    unknown = [v for v in vm_ids if v not in known]
    if unknown:
        raise ValueError(f"unknown VM(s) {unknown}")
    inter = topology.interconnect()
    index = {inter[i]: i for i in inter.node_indices()}
    if not rx.is_connected(inter.subgraph([index[v] for v in vm_ids])):
        raise ValueError(f"VMs {vm_ids} are not connected")
    vm_ids = topology.canonical_vms(vm_ids)

    count: dict[int, int] = {}
    for v in vm_ids:
        for number in topology.vm(v).connectors():
            count[number] = count.get(number, 0) + 1

    # Deterministic numbering: VMs in declaration
    # order, then each VM's node order; a merged connector gets the index of
    # its first occurrence.
    graph = rx.PyGraph()
    origins: list[list[Origin]] = []
    merged: dict[int, int] = {}  # connector number -> fused index

    def add(node: Node, origin: Origin) -> int:
        origins.append([origin])
        return graph.add_node(node)

    for v in vm_ids:
        src = topology.vm(v).graph
        new: dict[int, int] = {}  # VM index -> fused index
        for i in src.node_indices():
            node = src[i]
            if node.kind == "qubit":
                new[i] = add(Node("qubit", f"{v}:{node.label}"), (v, node.label))
                continue
            number = connector_number(node.label)
            if count[number] != 2:
                continue  # its other VM is not fused: dropped
            if number in merged:
                origins[merged[number]].append((v, node.label))
            else:
                merged[number] = add(Node("qubit", node.label), (v, node.label))
            new[i] = merged[number]
        for a, b in src.edge_list():
            if a in new and b in new:
                graph.add_edge(new[a], new[b], None)
    return FusedGraph(graph, origins)


def fusion_candidates(topology: VirtualTopology, num_qubits: int) -> list[list[str]]:
    """Connected groups of at least two VMs whose fusion has >= `num_qubits` qubits.

    Sorted by fused size (smallest first), ties in enumeration order (groups
    of 2 VMs, then 3..., each in `topology.vms` order). A helper for the user,
    not an automatic choice. Exponential in the number of VMs.
    """
    found: list[tuple[int, list[str]]] = []
    vm_ids = [vm.name for vm in topology.vms]
    for k in range(2, len(vm_ids) + 1):
        for group in combinations(vm_ids, k):
            try:
                size = fuse(topology, list(group)).num_qubits
            except ValueError:  # not connected
                continue
            if size >= num_qubits:
                found.append((size, list(group)))
    found.sort(key=lambda item: item[0])  # stable: keeps enumeration order
    return [group for _, group in found]


# ---------------------------------------------------------------- loading


def topology_from_dicts(
    categories_dict: dict[str, Any], vms_dict: dict[str, Any] | None = None
) -> VirtualTopology:
    """Build and validate a VirtualTopology.

    categories_dict: {"basis_gates": [Qiskit names],
                      "categories": [{"name": name, "qubits": [labels], "edges": [[a, b], ...]}]}
    vms_dict:        {"vms": [{"name": name, "category": category name, "connectors": {"<n>": [labels]}}]}
                     (optional; without it, `vms` is empty).

    Raises ValueError on any inconsistency (unknown label or category,
    duplicate label, connector not in exactly two VMs...).
    """
    categories: dict[str, Category] = {}
    for c in categories_dict["categories"]:
        cid = c["name"]
        if cid in categories:
            raise ValueError(f"duplicate category name(s) {[cid]}")
        graph = rx.PyGraph()
        for label in c["qubits"]:
            graph.add_node(Node("qubit", label))
        by_label = labels(graph)
        if len(by_label) != graph.num_nodes():
            raise ValueError(f"category {cid}: duplicate labels")
        for a, b in c["edges"]:
            if a not in by_label or b not in by_label:
                raise ValueError(f"category {cid}: edge on unknown label {[a, b]}")
            graph.add_edge(by_label[a], by_label[b], None)
        categories[cid] = Category(cid, graph)
    vms: list[VM] = []
    for v in (vms_dict or {"vms": []})["vms"]:
        if v["category"] not in categories:
            raise ValueError(f"{v['name']}: unknown category {v['category']!r}")
        connectors = {int(n): list(attached) for n, attached in v["connectors"].items()}
        vms.append(VM.build(v["name"], categories[v["category"]], connectors))
    topology = VirtualTopology(list(categories_dict["basis_gates"]), list(categories.values()), vms)
    topology.validate()
    return topology


def target(graph: rx.PyGraph, basis_gates: list[str]) -> Target:
    """Qiskit Target for `graph`: `basis_gates` (+ "measure" if missing) on
    `graph.num_nodes()` qubits, 2-qubit gates on the graph edges in both
    directions."""
    gates = list(basis_gates) + ([] if "measure" in basis_gates else ["measure"])
    return Target.from_configuration(
        basis_gates=gates,
        num_qubits=graph.num_nodes(),
        coupling_map=CouplingMap(graph.to_directed().edge_list()),
    )
