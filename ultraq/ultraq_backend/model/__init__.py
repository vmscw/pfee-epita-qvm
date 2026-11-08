"""Data representation: the physical chip, the virtual topology, the layout tying them, the jobs.

- `chips`: `PhysicalChip` (qubits, couplers, calibration), one class per real chip.
- `vm`: `Category` (a VM shape), `VM` (an instance of a category), `Node`.
- `virtual_topology`: `VirtualTopology` (categories + VMs), `fuse`, `fusion_candidates`, `target`.
- `chip_layout`: `ChipLayout` = a `PhysicalChip` + a `VirtualTopology` + the `mapping` to physical qubits.
- `jobs`: `Job`, `Decision`, `PlacedJob`, `Batch`.

No execution logic here; this package never imports `ultraq_backend.steps`.
"""
