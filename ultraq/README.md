# ultraq — multiprogramming of quantum virtual machines (qVMs)

ultraq runs **several quantum programs at the same time on one chip** by cutting it into **quantum virtual machines (qVMs)**. The design follows **HyperQ** (OSDI'25).

- The chip is a real one, **IQM Garnet** (20 qubits) or **IQM Emerald** (54 qubits), built from a **calibration snapshot** fetched from IQM Resonance and cached locally.
- A **layout** cuts the chip into VMs. By default the whole chip is one VM; a layout file gives several VMs, possibly linked by *connectors*. Two are shipped (see below).
- A **hypervisor** (`ultraq_backend.Hypervisor`) queues circuits, places them on free VMs, combines them into one circuit, runs it and gives each job its own counts.
- Users write **plain Qiskit** through `ultraq_qiskit_connector`: `transpile(qc, backend)`, `backend.run(qc)`, `job.result().get_counts()`.
- Execution runs on **Aer** (no noise model) or, as-is, on the **real IQM chip** through iqm-client (`Hypervisor(chip, executor=IQMExecutor(chip))`).

## Install and run

From the project root `ultraq/` (ignore uv's `VIRTUAL_ENV` warning):

```bash
uv sync
uv run python -m ultraq_backend.model.chips garnet    # fetch + cache a Garnet snapshot
```

Fetching needs the IQM Resonance server in `IQM_URL` and a token in `IQM_CALIBRATION_TOKEN` (environment or `.env`); running on the real QPU needs `IQM_TOKEN`. Snapshots go to `calibration_data/garnet/<UTC timestamp>/` (gitignored).

## Minimal example

The whole chip as one VM (no layout needed). Runs offline once a snapshot is cached:

```python
from qiskit import QuantumCircuit, transpile
from ultraq_backend import Hypervisor
from ultraq_backend.model.chips import IQMGarnet
from ultraq_qiskit_connector import UltraqProvider

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

with Hypervisor(IQMGarnet.load()) as hv:          # latest cached snapshot
    backend = UltraqProvider(hv).get_backend("chip")
    job = backend.run(transpile(qc, backend), shots=1000)
    print(job.result().get_counts())              # {'00': 503, '11': 497}
```

The hypervisor runs its queue in a background thread; leaving the `with` block (or `hv.stop()`) stops it. To cut the chip into several VMs, pass a `ChipLayout` (`ChipLayout.from_dict` or `ChipLayout.from_file`) or the path of a layout file.

## Default layouts

`ultraq_backend/model/chips/default_layout/` holds two layouts:

- `default_iqm_garnet.json`: 4 VMs of category S4 (2×2 square) and 4 connectors;
- `default_iqm_emerald.json`: 4 VMs of category S9 (3×3 square) and 5 connectors.

```python
from ultraq_backend.model.chip_layout import ChipLayout

layout = ChipLayout.from_file("ultraq_backend/model/chips/default_layout/default_iqm_garnet.json")
hv = Hypervisor(layout)          # or Hypervisor("<same path>"), relative to the current directory
layout.plot("garnet.png")        # draw it (needs `uv sync --extra plot`)
```

A layout describes the chip as if everything were on. Loaded on a snapshot where a qubit or coupler it uses is off, it is pruned with a warning: the VM becomes smaller (in a category such as `S4~1`, backend `ultraq_S4~1`) and a connector without a usable link is removed.

## Tree

```
ultraq/
├── ultraq_backend/            # the core
│   ├── hypervisor.py          # Hypervisor: submit / status / result, background queue
│   ├── model/                 # data only: chips/, vm.py, virtual_topology.py, chip_layout.py, jobs.py
│   └── steps/                 # validation -> scheduler -> mapping -> executor
├── ultraq_qiskit_connector/   # Qiskit interface: UltraqProvider, CategoryBackend, FusedBackend, UltraqJob
└── calibration_data/          # snapshot cache (gitignored)
```

## Current limits

- **Aer only**, ideal simulation: the calibration is not used for a noise model.
- Only **HyperQ pass 1** (spatial placement) is implemented; the scheduler ignores the calibration.
- Cuts into several VMs are **written by hand**; an inactive qubit or coupler only shrinks the VMs that use it (no automatic re-cut).

## License

Apache License 2.0, see [LICENSE](../LICENSE) at the repository root.
