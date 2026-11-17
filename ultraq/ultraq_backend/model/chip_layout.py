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

The chip is built from a cached calibration snapshot (`ultraq_backend.model.chips.load_chip`).
A layout file describes the chip as if everything were available: `from_dict`
drops every qubit, coupler or connector it uses that is off in the snapshot
(one warning per VM / connector), so VMs may come out smaller, in a category
`<category>~<k>` when no declared category has their new shape. The
`basis_gates` of the topology are the chip's native gates. `ChipLayout.plot`
draws the layout on the chip (optional `plot` extra, matplotlib).
This module must not know the scheduling, the executor nor any specific
vendor or gate name.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rustworkx as rx

from ultraq_backend.model.chips import CACHE_ROOT, PhysicalChip, load_chip
from ultraq_backend.model.virtual_topology import VirtualTopology, topology_from_dicts
from ultraq_backend.model.vm import connector_number

log = logging.getLogger(__name__)


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
        topology = self.virtual_topology
        log.info(
            "Layout built: chip %s, snapshot %s, %d categories, %d VMs, %d physical qubits used",
            self.physical_chip.id, self.physical_chip.snapshot, len(topology.categories),
            len(topology.vms), len({p for m in self.mapping.values() for p in m.values()}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], root: str | Path = CACHE_ROOT) -> ChipLayout:
        """Build from the file format (see the module docstring).

        The chip is loaded with `load_chip(data["chip"], data.get("snapshot",
        "latest"), root)`; the topology gets the chip's gates as `basis_gates`.

        The elements the layout uses that are off in the snapshot are dropped
        first, with one warning per VM and per removed connector:
        - a plain qubit on an inactive qubit (with its edges), an edge on an
          inactive coupler;
        - then, in each VM, plain qubits left without any edge (unless the
          category has no edge at all) and, if the VM is disconnected, every
          component but the largest (ties: the one with the lowest label);
        - a connector on an inactive qubit, or left without any attachment
          (on an active coupler, to a kept qubit) in one of its two VMs, is
          removed from both;
        - a VM without any qubit left is removed; none left: ValueError.
        A reduced VM joins the first declared category whose graph is
        isomorphic to its new plain-qubit graph (its labels renamed through
        the isomorphism), else a new category `<category>~<k>` (k = 1, 2...,
        labels q0.. in the original label order) that later reduced VMs of
        the same shape join. A category whose VMs all moved is dropped.

        Raises KeyError for an unknown chip, FileNotFoundError for a missing
        snapshot, ValueError for an invalid layout.
        """
        chip = load_chip(data["chip"], data.get("snapshot", "latest"), root)
        categories, vms, mapping = _prune(chip, data)
        topology = topology_from_dicts(
            {"basis_gates": _gates(chip), "categories": categories}, {"vms": vms}
        )
        return cls(physical_chip=chip, virtual_topology=topology, mapping=mapping)

    @classmethod
    def whole_chip(cls, chip: PhysicalChip) -> ChipLayout:
        """The default layout: the whole chip as one category "chip" and one VM "chip".

        Nodes "q0", "q1"... are the active qubits in index order (node i =
        `chip.active_qubits[i]`), edges are the active couplers. Inactive
        qubits are left out, so node indices may differ from physical indices.
        """
        log.debug("Whole-chip layout for %s (snapshot %s)", chip.id, chip.snapshot)
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
        log.debug("Loading layout file %s", path)
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

    def plot(self, path: str | Path | None = None):
        """Draw the layout on the chip; save a PNG to `path`, or return the matplotlib Figure if None.

        Every physical coupler is a line with a diamond at its middle; one
        colour per VM (its qubits and couplers); connector qubits are white
        with a dark outline, their links dark; unused qubits and couplers are
        grey; what is off in the snapshot is marked in red (an "x" on a
        coupler, the outline of a qubit). Positions are `physical_chip.positions`
        (a spring layout if None). Needs matplotlib (`uv sync --extra plot`):
        ImportError otherwise.
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.colors import to_rgb
            from matplotlib.lines import Line2D
            from matplotlib.patches import Patch
        except ImportError:
            raise ImportError("ChipLayout.plot needs matplotlib: run `uv sync --extra plot`") from None
        chip = self.physical_chip
        xy = chip.positions or {i: tuple(p) for i, p in rx.spring_layout(chip.graph, seed=1).items()}
        palette = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2", "#EECA3B", "#9D755D", "#FF9DA6", "#BAB0AC"]
        colour = {vm.name: palette[i % len(palette)] for i, vm in enumerate(self.virtual_topology.vms)}
        owner: dict[int, str] = {}  # physical qubit -> VM name (plain qubits)
        connector: dict[int, str] = {}  # physical qubit -> connector label
        link: dict[frozenset[int], str] = {}  # used coupler -> its colour
        for vm in self.virtual_topology.vms:
            m = self.mapping[vm.name]
            for node in vm.graph.nodes():
                if node.kind == "connector":
                    connector[m[node.label]] = node.label
                else:
                    owner[m[node.label]] = vm.name
            for a, b in vm.graph.edge_list():
                plain = vm.graph[a].kind == vm.graph[b].kind == "qubit"
                link[frozenset((m[vm.graph[a].label], m[vm.graph[b].label]))] = colour[vm.name] if plain else "#333333"

        fig, ax = plt.subplots(figsize=(1.5 * chip.num_qubits**0.5 + 0.5,) * 2)
        for a, b, coupler in chip.graph.weighted_edge_list():
            (x1, y1), (x2, y2) = xy[a], xy[b]
            line = link.get(frozenset((a, b)), "#cccccc")
            width = 6 if line in colour.values() else 3 if line == "#333333" else 2
            ax.plot([x1, x2], [y1, y2], color=line, lw=width, zorder=1)
            middle = ((x1 + x2) / 2, (y1 + y2) / 2)
            ax.scatter(*middle, marker="D", s=200, color=line if line != "#cccccc" else "#dddddd", edgecolor="white", zorder=2)
            if not coupler.active:
                ax.scatter(*middle, marker="x", s=260, color="#d62728", linewidths=3.5, zorder=5)
        for p, (x, y) in xy.items():
            face = colour[owner[p]] if p in owner else "white"
            edge = "#333333" if p in connector else "white" if p in owner else "#bbbbbb"
            if not chip.qubit(p).active:
                edge = "#d62728"
            ax.scatter(x, y, s=1150, color=face, edgecolor=edge, linewidth=2.5, zorder=3)
            r, g, b = to_rgb(face)
            text = "white" if p in owner and 0.299 * r + 0.587 * g + 0.114 * b < 0.6 else "#222222"
            label = chip.qubit(p).label + (f"\n{connector[p]}" if p in connector else "")
            ax.text(x, y, label, ha="center", va="center", fontsize=8, color=text, weight="bold", zorder=4)
        legend = [Patch(color=colour[vm.name], label=f"{vm.name} ({vm.category.name})") for vm in self.virtual_topology.vms]
        legend += [
            Patch(facecolor="white", edgecolor="#333333", label="connector"),
            Patch(color="#333333", label="connector link (fusion only)"),
            Patch(color="#cccccc", label="unused coupler"),
            Line2D([], [], marker="x", color="#d62728", lw=0, markersize=12, markeredgewidth=3,
                   label=f"inactive ({chip.snapshot})"),
        ]
        ax.legend(handles=legend, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=10)
        ax.set_title(f"{chip.name} — {chip.snapshot}", fontsize=13)
        ax.set_aspect("equal")
        ax.axis("off")
        if path is None:
            return fig
        fig.savefig(path, dpi=110, bbox_inches="tight")
        plt.close(fig)
        return None

    @property
    def num_physical_qubits(self) -> int:
        """Size of the physical register: the chip's number of qubits."""
        return self.physical_chip.num_qubits


def _prune(chip: PhysicalChip, data: dict[str, Any]) -> tuple[list[dict], list[dict], dict[str, dict[str, int]]]:
    """Categories, VMs and mapping of a layout dict without the elements off in the snapshot (see `from_dict`).

    Anything unknown (label, qubit, category) is kept as is for
    `topology_from_dicts` and `ChipLayout.check` to report.
    """

    def qb(p: int) -> str:
        return chip.qubit(p).label

    def off_qubit(p: int | None) -> bool:
        return p is not None and 0 <= p < chip.num_qubits and not chip.qubit(p).active

    def off_coupler(a: int | None, b: int | None) -> bool:
        return None not in (a, b) and chip.graph.has_edge(a, b) and not chip.coupler(a, b).active

    categories = list(data["categories"])
    by_name = {c["name"]: c for c in categories}
    mapping = {vm: {label: int(p) for label, p in m.items()} for vm, m in data["mapping"].items()}
    kept = {}  # vm name -> (plain qubits kept, edges kept, why the others were dropped)
    dead: dict[int, tuple[int, list[str]]] = {}  # removed connector number -> (physical qubit, why)
    for v in data["vms"]:
        cat, m = by_name.get(v["category"]), mapping.get(v["name"])
        if cat is None or m is None:
            continue
        why = [f"{qb(m[q])} inactive" for q in cat["qubits"] if off_qubit(m.get(q))]
        plain = [q for q in cat["qubits"] if not off_qubit(m.get(q))]
        edges = []
        for a, b in cat["edges"]:
            if a in plain and b in plain:
                if off_coupler(m.get(a), m.get(b)):
                    why.append(f"coupler {qb(m[a])}-{qb(m[b])} inactive")
                else:
                    edges.append((a, b))
        parts = [c for c in rx.connected_components(_graph(plain, edges)) if len(c) > 1 or not cat["edges"]]
        largest = max(parts, key=lambda c: (len(c), -min(c)), default=set())
        why += [f"{qb(m[q])} cut off from the rest of the VM" for i, q in enumerate(plain) if i not in largest]
        plain = [q for i, q in enumerate(plain) if i in largest]
        edges = [(a, b) for a, b in edges if a in plain and b in plain]
        kept[v["name"]] = (plain, edges, why)
        for n, attached in v["connectors"].items():
            p = m.get(f"c{n}")
            if off_qubit(p):
                dead.setdefault(int(n), (p, []))[1].append(f"{qb(p)} inactive")
            elif p is not None and not any(a in plain and not off_coupler(p, m.get(a)) for a in attached):
                links = [
                    f"{qb(p)}-{qb(m[a])} inactive" if off_coupler(p, m.get(a)) else f"{qb(m[a])} dropped"
                    for a in attached if a in m
                ]
                dead.setdefault(int(n), (p, []))[1].append(f"no active link to {v['name']} ({', '.join(links)})")
    for n, (p, why) in sorted(dead.items()):
        log.warning("Layout: connector c%d (%s) removed: %s (snapshot %s)", n, qb(p), "; ".join(why), chip.snapshot)

    vms = []
    for v in data["vms"]:
        if v["name"] not in kept:
            vms.append(v)
            continue
        plain, edges, why = kept[v["name"]]
        m = mapping[v["name"]]
        cat = by_name[v["category"]]
        connectors = {
            n: [a for a in attached if a in plain and not off_coupler(m.get(f"c{n}"), m.get(a))]
            for n, attached in v["connectors"].items()
            if int(n) not in dead
        }
        if not plain:
            log.warning("Layout: %s removed, no qubit left: %s (snapshot %s)", v["name"], ", ".join(why), chip.snapshot)
            del mapping[v["name"]]
            continue
        rename = {q: q for q in plain}
        category = v["category"]
        if len(plain) != len(cat["qubits"]) or len(edges) != len(cat["edges"]):
            reduced = _graph(plain, edges)
            for c in categories:
                match = next(rx.vf2_mapping(_graph(c["qubits"], c["edges"]), reduced), None)
                if match is not None:
                    category, rename = c["name"], {plain[r]: c["qubits"][i] for i, r in match.items()}
                    break
            else:
                category = f"{v['category']}~{1 + sum(c['name'].startswith(v['category'] + '~') for c in categories)}"
                rename = {q: f"q{i}" for i, q in enumerate(plain)}
                categories.append({
                    "name": category,
                    "qubits": [rename[q] for q in plain],
                    "edges": [[rename[a], rename[b]] for a, b in edges],
                })
            log.warning(
                "Layout: %s reduced to %d qubits (%s), category %s -> %s (snapshot %s)",
                v["name"], len(plain), ", ".join(why), v["category"], category, chip.snapshot,
            )
        vms.append({
            "name": v["name"],
            "category": category,
            "connectors": {n: [rename[a] for a in attached] for n, attached in connectors.items()},
        })
        keep = set(plain) | {f"c{n}" for n in connectors}
        mapping[v["name"]] = {rename.get(q, q): p for q, p in m.items() if q in keep}
    if not vms:
        raise ValueError(f"layout: no VM left on chip {chip.id!r} (snapshot {chip.snapshot})")
    used_before = {v["category"] for v in data["vms"]}
    used = {v["category"] for v in vms}
    return [c for c in categories if c["name"] in used or c["name"] not in used_before], vms, mapping


def _graph(qubits: list[str], edges: list) -> rx.PyGraph:
    """Undirected graph of labelled qubits (node i = qubits[i], payload = label)."""
    graph = rx.PyGraph()
    index = {q: graph.add_node(q) for q in qubits}
    graph.add_edges_from_no_data([(index[a], index[b]) for a, b in edges])
    return graph


def _gates(chip: PhysicalChip) -> list[str]:
    """The chip's native gates in Qiskit names, without "measure" (topology form)."""
    return [g for g in chip.qiskit_basis_gates() if g != "measure"]
