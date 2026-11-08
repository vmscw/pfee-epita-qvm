# The model: chip, VMs, layout

The data objects of `ultraq_backend/model/`, on a small example. How the steps use them: [architecture.md](architecture.md).

## Three layers

- **`PhysicalChip`** (`model/chips/`): the real chip in one calibration snapshot. A graph: node = qubit, edge = coupler, each marked `active` or not. Never written by hand, built by `IQMGarnet.load()` / `.fetch()` (see [calibration.md](calibration.md)). Inactive qubits stay in the graph, so indices are stable (Garnet: index = QB number - 1).
- **`VirtualTopology`** (`model/virtual_topology.py`): what users and the scheduler see: categories and VMs.
- **`ChipLayout`** (`model/chip_layout.py`): ties the two with a `mapping` `{vm: {label: physical qubit}}`. Only the mapping step reads it.

## Notions

- **Category**: a VM shape, a graph of qubits `q0`, `q1`... Users compile for a category.
- **VM**: an instance of a category placed on the chip: the category graph, followed by its connectors.
- **Connector**: a node `c<n>` shared by **exactly two VMs** (one physical qubit). It is used only when those two VMs are fused; otherwise it stays idle, as a buffer between them.
- **Fusion**: one graph made of a connected group of VMs; their shared connectors become ordinary qubits. Used for circuits too big for every category.

All graphs are undirected `rustworkx.PyGraph` with indices `0..n-1`. **Circuit qubit `i` = node `i`** of the graph it was compiled for.

## Default layout: the whole chip

`Hypervisor(chip)` uses `ChipLayout.whole_chip(chip)`: one category `"chip"` and one VM `"chip"`, made of the active qubits and couplers. Node `i` is `chip.active_qubits[i]` (on Garnet with QB14 off, 19 nodes, so node 13 is QB15).

## Example: two 2x2 VMs and a connector

Garnet, a category `S4` (2x2 square), two VMs, and QB10 as connector `c1` between them:

```
 vm1                       vm2
 QB1 ── QB2                QB6 ── QB7
  │      │                  │      │
 QB4 ── QB5 ── (QB10 c1) ── QB11 ── QB12
```

A hand-written cut is a dict (or a JSON file for `ChipLayout.from_file`). Run from the project root, with a cached Garnet snapshot:

```python
from ultraq_backend import ChipLayout
from ultraq_backend.model.virtual_topology import fuse

layout = ChipLayout.from_dict({
    "chip": "garnet",                     # optional "snapshot": "<timestamp>", default latest
    "categories": [{"name": "S4", "qubits": ["q0", "q1", "q2", "q3"],
                    "edges": [["q0", "q1"], ["q0", "q2"], ["q1", "q3"], ["q2", "q3"]]}],
    "vms": [{"name": "vm1", "category": "S4", "connectors": {"1": ["q3"]}},   # c1 attached to q3
            {"name": "vm2", "category": "S4", "connectors": {"1": ["q2"]}}],  # c1 attached to q2
    "mapping": {"vm1": {"q0": 0, "q1": 1, "q2": 3, "q3": 4, "c1": 9},
                "vm2": {"q0": 5, "q1": 6, "q2": 10, "q3": 11, "c1": 9}},
})
topo = layout.virtual_topology
print(topo.basis_gates)                            # ['r', 'cz'] (from the chip)
print([n.label for n in topo.vm("vm1").graph.nodes()])   # ['q0', 'q1', 'q2', 'q3', 'c1']

fused = fuse(topo, ["vm1", "vm2"])
print(fused.num_qubits)                            # 9 = 4 + 4 + c1
print(topo.fusion_candidates(6))                   # [['vm1', 'vm2']]
```

The fused graph numbers the nodes VM by VM (`vm1:q0`... `vm1:q3`, `c1`, `vm2:q0`... `vm2:q3`), the merged connector at its first occurrence. `fused.origins[i]` says which VM node(s) are behind node `i`; the mapper uses it to get the physical qubits (`[0, 1, 3, 4, 9, 5, 6, 10, 11]` here).

The group is always taken in **declaration order**: `fuse(topo, ["vm2", "vm1"])` is the same graph, and the backend is named `ultraq_vm1+vm2`. `fuse` raises `ValueError` for an empty, duplicated, unknown or non-connected group.

`fuse(topo, ["vm1"])` has exactly the shape of the category (connectors dropped): the mapper handles a category job on `vm1` this way.

## Placement rule

- **Category job** (`get_backend("S4")`): placed on the first free VM of the category, in declaration order. Never on a VM of another category.
- **Fused job** (`get_backend(vms=["vm1", "vm2"])`): runs on exactly these VMs, and waits until they are all free. A newer job may pass it.
- A category without any VM is accepted, but its jobs end in `ERROR`.

## Invariants

Checked when the topology is built (`VirtualTopology.validate`):

- unique category and VM names, unique labels, indices `0..n-1`;
- a connector is attached to category qubits only, and its number appears in **exactly two VMs**.

Checked by `ChipLayout.check` (at construction):

- the basis gates are the chip's;
- every node of every VM is mapped, to an **active** qubit, and no qubit is used twice (a connector is the same qubit in its two VMs);
- every VM edge is an **active** coupler.

So a hand-written cut is valid for its snapshot only: if a qubit it uses is off on another day, it fails to load.
