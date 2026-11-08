"""ultraq: multiprogramming of quantum VMs (qVMs), inspired by HyperQ (OSDI'25).

Everything runs in one process. The core is used through `Hypervisor`; the
Qiskit interface (provider, backends, jobs) is the separate package
`ultraq_qiskit_connector`, built on top of it:

    from qiskit import transpile
    from ultraq_backend import Hypervisor
    from ultraq_backend.model.chips import load_chip

    with Hypervisor(load_chip("garnet")) as hv:      # the whole chip as one VM "chip", Aer
        isa = transpile(circuit, target=hv.virtual_topology.target(category="chip"))
        job_id = hv.submit(isa, category="chip", shots=1000)
        counts = hv.result(job_id)

A `ChipLayout` (or a layout JSON path) instead of the chip cuts it into several VMs.

Packages:

- `model`: data representation, no execution logic. `model.chips` (the
  physical chip, built from fetched calibration data), `model.vm` and
  `model.virtual_topology` (the virtual side: categories and VMs, then the
  whole topology and fusion), `model.chip_layout` (ChipLayout: a chip cut into
  VMs), `model.jobs` (what flows between the steps).
- `steps`: transform one representation into the next, in the order a job
  goes through them: `validation` (accept a circuit), `scheduler` (HyperQ
  pass 1: job -> VMs), `mapping` (VMs -> physical qubits), `executor`
  (composite circuit + run -> counts).
- `hypervisor`: chains the steps (queue, statuses, run loop).

`model` never imports `steps`; `ultraq_backend` never imports `ultraq_qiskit_connector`.
"""

from ultraq_backend.hypervisor import Hypervisor
from ultraq_backend.model.chip_layout import ChipLayout

__all__ = ["ChipLayout", "Hypervisor"]
