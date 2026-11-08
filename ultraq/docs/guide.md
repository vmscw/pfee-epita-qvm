# User guide

ultraq runs in your own process: build a `Hypervisor` on a chip, wrap it in an
`UltraqProvider`, and write ordinary Qiskit. Jobs run on Aer (ideal simulation, no noise).

- [1. Quick start](#1-quick-start)
- [2. Cutting the chip into VMs](#2-cutting-the-chip-into-vms)
- [3. Fusing VMs](#3-fusing-vms)
- [4. Several users, one batch](#4-several-users-one-batch)
- [5. Jobs and errors](#5-jobs-and-errors)
- [6. Chips and calibration](#6-chips-and-calibration)
- [7. API reference](#7-api-reference)

The model (categories, VMs, connectors, fusion) is in [model.md](model.md), the code
layout in [architecture.md](architecture.md), the calibration data in
[calibration.md](calibration.md), next steps in [extending.md](extending.md).

The Python blocks below run in order, in one namespace, from the project root, offline
(cached Garnet snapshot `20261108T115135Z`). Counts vary from run to run.

## 1. Quick start

Fetch the chip calibration once (needs an IQM token, see [calibration.md](calibration.md)):

<!-- no-test -->
```bash
uv run python -m ultraq_backend.model.chips garnet
```

Then, offline:

```python
from qiskit import QuantumCircuit, transpile

from ultraq_backend import ChipLayout, Hypervisor
from ultraq_backend.model.chips import IQMGarnet
from ultraq_qiskit_connector import UltraqProvider


def ghz(n):
    qc = QuantumCircuit(n, n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.measure(range(n), range(n))
    return qc


chip = IQMGarnet.load()                    # latest cached snapshot (IQMGarnet.fetch() = network)
with Hypervisor(chip) as hv:               # default layout: the whole chip as one VM
    backend = UltraqProvider(hv).get_backend("chip")
    job = backend.run(transpile(ghz(4), backend), shots=1000)
    print(job.result().get_counts())       # {'0000': 503, '1111': 497}
```

`Hypervisor(chip)` uses `ChipLayout.whole_chip(chip)`: one category `"chip"` and one VM
`"chip"` made of the **active** qubits and couplers only (node `i` =
`chip.active_qubits[i]`, so on Garnet, where QB14 is off, nodes and physical indices
differ from QB15 on). A background thread runs the queue every `interval` seconds
(default 0.5); leaving the `with` block calls `hv.stop()`.

## 2. Cutting the chip into VMs

To run several jobs side by side, cut the chip by hand: a dict (or the same thing as a
JSON file) with `chip`, an optional `snapshot` (default `"latest"`), `categories`, `vms`
and `mapping`. Here two 2×2 squares (category `S4`) and one path of 3 (category `L3`);
`vm3` shares connector `c1` (QB9) with `vm1`:

```python
cut = {
    "chip": "garnet",
    "categories": [
        {"name": "S4", "qubits": ["q0", "q1", "q2", "q3"],
         "edges": [["q0", "q1"], ["q0", "q2"], ["q1", "q3"], ["q2", "q3"]]},
        {"name": "L3", "qubits": ["q0", "q1", "q2"], "edges": [["q0", "q1"], ["q1", "q2"]]},
    ],
    "vms": [
        {"name": "vm1", "category": "S4", "connectors": {"1": ["q2"]}},
        {"name": "vm2", "category": "S4", "connectors": {}},
        {"name": "vm3", "category": "L3", "connectors": {"1": ["q1"]}},
    ],
    "mapping": {                                # physical index on the chip: QB1 -> 0, ...
        "vm1": {"q0": 0, "q1": 1, "q2": 3, "q3": 4, "c1": 8},
        "vm2": {"q0": 5, "q1": 6, "q2": 10, "q3": 11},
        "vm3": {"q0": 2, "q1": 7, "q2": 12, "c1": 8},
    },
}
layout = ChipLayout.from_dict(cut)              # or ChipLayout.from_file("my_layout.json")
hv = Hypervisor(layout)                         # or Hypervisor("my_layout.json")
provider = UltraqProvider(hv)
print([b.name for b in provider.backends()])    # ['ultraq_L3', 'ultraq_S4']

backend = provider.get_backend("S4")            # the hypervisor picks a free S4 VM
counts = backend.run(transpile(ghz(4), backend), shots=1000).result().get_counts()
print(counts)                                   # {'1111': 488, '0000': 512}
```

- `categories`: VM shapes; the `i`-th label is circuit qubit `i`; undirected edges.
- `vms`: instances of a category, in declaration order (= placement order).
  `"connectors": {"<n>": [labels]}` adds node `c<n>` linked to those qubits; each
  number appears in exactly two VMs.
- `mapping`: physical qubit index of every node (`q…` and `c…`) of every VM.

Loading checks everything against the snapshot and raises `ValueError` (an unknown
chip gives `KeyError`, a missing snapshot `FileNotFoundError`): unknown labels, a qubit
used twice, a connector mapped to two different qubits, a node on an **inactive** qubit,
an edge that is not an **active** coupler... A cut is therefore valid for its snapshot
only. A relative path given to `Hypervisor` is resolved against the project root;
`ChipLayout.from_file` uses the current directory.

## 3. Fusing VMs

No category has 6 qubits. Fuse connected VMs: the job then runs on exactly those VMs
and waits until they are all free.

```python
print(provider.backends(min_qubits=6))          # []
print(provider.fusion_candidates(6))            # [['vm1', 'vm3']]

fused = provider.get_backend(vms=["vm3", "vm1"])   # order does not matter
print(fused.name, fused.num_qubits)             # ultraq_vm1+vm3 8
print([n.label for n in fused.graph.nodes()])
# ['vm1:q0', 'vm1:q1', 'vm1:q2', 'vm1:q3', 'c1', 'vm3:q0', 'vm3:q1', 'vm3:q2']

counts = fused.run(transpile(ghz(6), fused), shots=1000).result().get_counts()
print(counts)                                   # {'000000': 498, '111111': 502}
```

A fused group is always taken in declaration order, so `["vm3", "vm1"]` and
`["vm1", "vm3"]` are the same backend. A connector shared by two fused VMs becomes one
qubit `c<n>`; connectors to VMs outside the group are dropped (see [model.md](model.md)).

## 4. Several users, one batch

`backend.run` only queues the job. Jobs queued within the same `interval` share a batch
(if they have the same shots):

```python
jobs = {user: backend.run(transpile(ghz(4), backend), shots=500) for user in ("alice", "bob")}
for user, job in jobs.items():
    print(user, job.result().get_counts())      # alice {'0000': 262, '1111': 238} ...

owner = {job.job_id(): user for user, job in jobs.items()}
print([(owner[i], vms) for i, vms in hv.history[-1]])   # [('alice', ['vm1']), ('bob', ['vm2'])]
```

The scheduler is HyperQ pass 1: jobs are tried in queue order, a category job takes the
first free VM of its category, a fused job needs all its VMs free, and a job that does
not fit waits for the next batch (later jobs may pass it). Only `hv.history` records
which VMs were used.

## 5. Jobs and errors

A job goes `QUEUED` → `RUNNING` → `DONE` or `ERROR`. The core enum is
`ultraq_backend.model.jobs.JobState` (a `StrEnum`, equal to its name); `UltraqJob.status()`
returns the matching `qiskit.providers.JobStatus`.

Errors at call time (the job never enters the queue), all `ValueError`:

| Message (abridged) | Fix |
|---|---|
| `cannot run as-is on category 'S4': non-native gate 'h'` | `transpile(qc, backend)` first |
| `cannot fuse ['vm2', 'vm3']: VMs ['vm2', 'vm3'] are not connected` | pick a group from `fusion_candidates(n)` |
| `unknown category 'XL' (available: ['L3', 'S4'])` | see `provider.backends()` |
| `shots must be a positive integer, got 0` | integer > 0 |
| `run() takes one QuantumCircuit (max_circuits = 1), got 2` | one `run` per circuit |

`transpile` itself raises `CircuitTooWideForTarget` for a circuit bigger than the backend.

```python
try:
    backend.run(ghz(4))                         # not transpiled
except ValueError as err:
    print(err)
# circuit 'circuit-…' cannot run as-is on category 'S4': non-native gate 'h' (native: ['cz', 'r']). ...
```

An accepted job can still fail: the executor raises, the scheduler or mapper raises, or
the job can never be placed (a category with no VM). The job is then `ERROR`, the cause is
in `hv.job(job_id).error`, `hv.result` raises `RuntimeError` and `job.result()` raises
Qiskit's `JobError`:

```python
from qiskit.providers import JobError


class Offline:                                  # any object with execute(batch, shots)
    def execute(self, batch, shots):
        raise RuntimeError("target offline")


with Hypervisor(layout, executor=Offline()) as hv_ko:
    s4 = UltraqProvider(hv_ko).get_backend("S4")
    job = s4.run(transpile(ghz(4), s4))
    try:
        job.result()
    except JobError as err:
        print(err)                              # 'job … failed: target offline'
    print(job.status(), repr(hv_ko.job(job.job_id()).error))
# JobStatus.ERROR RuntimeError('target offline')
```

`hv.stop()` stops the thread and runs what is left in the queue (idempotent); `submit`
after `stop()` raises `RuntimeError`. `hv.result(job_id, timeout=None)` always waits:
`TimeoutError` after `timeout` seconds, `RuntimeError` if the background thread died.

Without Qiskit backends, use the core directly:

```python
vt = hv.virtual_topology
job_id = hv.submit(transpile(ghz(3), target=vt.target(category="L3")), category="L3", shots=100)
print(hv.status(job_id), hv.result(job_id))     # QUEUED {'000': 48, '111': 52}
hv.stop()
```

## 6. Chips and calibration

A chip is built from a fetched calibration snapshot, cached under
`calibration_data/<chip>/<UTC timestamp>/` (gitignored): `IQMGarnet.fetch()` (network,
token) or `IQMGarnet.load()` / `load_chip("garnet")` (cache only).

```python
from ultraq_backend.model.chips import load_chip, snapshots

print(snapshots("garnet"))                      # ['20261108T115135Z']
chip = load_chip("garnet")                      # same as IQMGarnet.load()
print(chip.num_qubits, len(chip.active_qubits), chip.num_couplers, len(chip.active_couplers))
# 20 19 30 26
print(chip.qubit(0).label, chip.qubit(0).t1, chip.coupler(0, 1).gate_fidelity)
# QB1 1.6037357837543914e-05 {'cz': 0.9916367445830574}
```

The calibration values (T1, T2, fidelities, `chip.target()` with errors) are **not**
used yet: the layout only uses which qubits and couplers are active. Details in
[calibration.md](calibration.md).

## 7. API reference

### `ultraq_backend`

**`Hypervisor(chip_layout, executor=None, interval=0.5)`**: `chip_layout` is a
`PhysicalChip` (→ `ChipLayout.whole_chip`), a `ChipLayout` or a JSON path; starts the
background thread.

| Member | Description |
|---|---|
| `submit(circuit, *, category=None, vms=None, shots=1024) -> str` | check and queue; exactly one of `category` / `vms`; `ValueError`, `RuntimeError` after `stop()` |
| `job(job_id)`, `status(job_id)` | the `Job` / its `JobState`; `KeyError` if unknown |
| `result(job_id, timeout=None) -> dict[str, int]` | waits; counts, bit 0 rightmost |
| `stop()`, `with ... as hv:` | stop the thread, drain the queue |
| `chip_layout`, `virtual_topology` | the layout; categories, VMs, `graph(...)`, `target(...)`, `fusion_candidates(n)`, `canonical_vms(vms)` |
| `jobs`, `queue`, `history` | `{job_id: Job}`; waiting jobs; per batch `[(job_id, vms)]` |
| `executor`, `scheduler`, `mapper` | the steps (`Executor(backend=None, seed=None)` = Aer) |

**`ChipLayout(physical_chip, virtual_topology, mapping)`**: `whole_chip(chip)`,
`from_dict(data, root=CACHE_ROOT)`, `from_file(path, root=CACHE_ROOT)`, `check()` (run by
the constructor), `num_physical_qubits`.

**`ultraq_backend.model.virtual_topology`**: `VirtualTopology` (`category`, `vm`,
`vms_of`, `canonical_vms`, `graph`, `target`, `fusion_candidates`, `interconnect`),
`fuse(topology, vms) -> FusedGraph` (`graph`, `origins`, `num_qubits`).

**`ultraq_backend.model.chips`**: `CHIPS`, `load_chip(name, snapshot="latest", root=CACHE_ROOT)`,
`snapshots(qpu, root=CACHE_ROOT)`, `CACHE_ROOT`, `PhysicalChip`, `Qubit`, `Coupler`,
`RawMetric`, `IQMGarnet`, `IQMEmerald` (`fetch(...)`, `load(snapshot, root)`).

**`ultraq_backend.model.jobs`**: `JobState`, `Job` (`job_id`, `request`, `shots`,
`circuit`, `status`, `counts`, `error`), `PlacedJob`, `Batch`.

### `ultraq_qiskit_connector`

| Member | Description |
|---|---|
| `UltraqProvider(hv).backends(min_qubits=None)` | one `CategoryBackend` per category, smallest first |
| `UltraqProvider(hv).get_backend(name=None, *, vms=None)` | category backend (`"S4"` or `"ultraq_S4"`) or `FusedBackend` of `vms` |
| `UltraqProvider(hv).fusion_candidates(n)` | connected VM groups with ≥ `n` qubits, smallest first |
| `backend.target`, `backend.graph` | compile target; circuit qubit `i` = graph node `i` |
| `backend.run(qc, shots=1024, memory=False) -> UltraqJob` | one circuit; `seed_simulator` ignored, other unknown options warn |
| `job.status()`, `job.result()` | Qiskit `JobStatus`; Qiskit `Result` (waits; `JobError` on failure) |

`BackendSamplerV2(backend=backend)` works too. With `memory=True`, per-shot results are
rebuilt from the counts (shot order is not the measurement order).
