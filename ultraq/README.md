# ultraq — multiprogramming of quantum virtual machines (qVMs)

ultraq runs **several quantum programs at the same time on one chip** by cutting it into **quantum virtual machines (qVMs)**. The design follows **HyperQ** (OSDI'25).

- The chip is a real one, **IQM Garnet** (20 qubits) or **IQM Emerald** (54 qubits), built from a **calibration snapshot** fetched from IQM Resonance and cached locally.
- A **layout** cuts the chip into VMs. By default the whole chip is one VM; a hand-written cut gives several VMs, possibly linked by *connectors* (see [docs/model.md](docs/model.md)).
- A **hypervisor** (`ultraq_backend.Hypervisor`) queues circuits, places them on free VMs, combines them into one circuit, runs it and gives each job its own counts.
- Users write **plain Qiskit** through `ultraq_qiskit_connector`: `transpile(qc, backend)`, `backend.run(qc)`, `job.result().get_counts()`.
- Execution is **Aer only** for now, without noise model.

## Install and run

From the project root `ultraq/` (ignore uv's `VIRTUAL_ENV` warning):

```bash
uv sync
uv run python -m ultraq_backend.model.chips garnet    # fetch + cache a Garnet snapshot
uv run python examples/demo.py                        # 2 users share one batch on Aer
```

Fetching needs an IQM Resonance token in `IQM_TOKEN` (environment or `.env`). Snapshots go to `calibration_data/garnet/<UTC timestamp>/` (gitignored). See [docs/calibration.md](docs/calibration.md).

`examples/demo.py` fetches the calibration itself, cuts two 2x2 VMs out of Garnet (vm1 = QB1 QB2 QB4 QB5, vm2 = QB6 QB7 QB11 QB12), and alice and bob each run a GHZ-4. Output (counts vary):

```text
IQM Garnet snapshot 20261108T115135Z
alice: {'1111': 517, '0000': 483}
bob: {'0000': 510, '1111': 490}
history: [[('2254c7...', ['vm1']), ('b0a44b...', ['vm2'])]]
```

Both jobs ran in the same batch, one per VM.

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

The hypervisor runs its queue in a background thread; leaving the `with` block (or `hv.stop()`) stops it. To cut the chip into several VMs, pass a `ChipLayout` (see `examples/demo.py` and [docs/model.md](docs/model.md)).

## Tree

```
ultraq/
├── ultraq_backend/            # the core
│   ├── hypervisor.py          # Hypervisor: submit / status / result, background queue
│   ├── model/                 # data only: chips/, vm.py, virtual_topology.py, chip_layout.py, jobs.py
│   └── steps/                 # validation -> scheduler -> mapping -> executor
├── ultraq_qiskit_connector/   # Qiskit interface: UltraqProvider, CategoryBackend, FusedBackend, UltraqJob
├── examples/demo.py           # end-to-end demo
├── calibration_data/          # snapshot cache (gitignored)
└── docs/
```

## Documentation

- [docs/guide.md](docs/guide.md): using ultraq (layouts, fusion, errors, API).
- [docs/model.md](docs/model.md): the model (categories, VMs, connectors, fusion, placement).
- [docs/architecture.md](docs/architecture.md): code organisation and the path of a job.
- [docs/calibration.md](docs/calibration.md): IQM calibration data, fetch and cache.
- [docs/extending.md](docs/extending.md): ways to extend the project.

## Current limits

- **Aer only**, ideal simulation: the calibration is not used for a noise model.
- Only **HyperQ pass 1** (spatial placement) is implemented; the scheduler ignores the calibration.
- Cuts into several VMs are **written by hand** and valid for one snapshot (an inactive qubit or coupler makes them fail).

## License

Apache License 2.0, see [LICENSE](../LICENSE) at the repository root.
