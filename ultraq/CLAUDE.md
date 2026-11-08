# CLAUDE.md — ultraq

qVM multiprogramming inspired by HyperQ (OSDI'25), in a single process: a physical chip (IQM Garnet or Emerald, built from a fetched calibration snapshot) is cut into VMs; a `Hypervisor` queues circuits, places them on free VMs, maps them to physical qubits and runs them together on Aer. A separate package exposes all this as plain Qiskit (provider, virtual backends). Documentation: `README.md` and `docs/`.

Keep the code simple: no abstract class, registry or extension point until there are two implementations.

## Commands

From the project root `ultraq/` (ignore uv's `VIRTUAL_ENV` warning):

```bash
uv sync
uv run python -m ultraq_backend.model.chips garnet [--set default] [--out DIR]   # fetch + cache a snapshot (IQM_TOKEN in env or .env)
uv run python examples/demo.py                                                  # fetches Garnet itself (needs IQM_TOKEN), 2 users on Aer
```

Never read `.env` (it holds the IQM token).

Check changes with the demo or, offline, a script loading a cached snapshot (`IQMGarnet.load(root=...)`), since the demo needs the network.

## Map

Two packages. `ultraq_backend/` is the core and never imports `ultraq_qiskit_connector/`; inside the core, `model/` never imports `steps/`.

`ultraq_backend/`:

- `model/` — data only, no execution logic.
  - `chips/physical_chip.py`: `PhysicalChip`, `Qubit`, `Coupler`, `RawMetric`. Vendor-agnostic: coupling graph (node = `Qubit`, edge = `Coupler`), `active_qubits`, `active_couplers`, `qiskit_basis_gates`, `coupling_map`, `target` (with calibration errors).
  - `chips/iqm.py`: `IQMGarnet`, `IQMEmerald` (`fetch()` from the IQM Resonance API + cache, `load(snapshot)` from the cache, no network), `snapshots`, `CACHE_ROOT`. The only module that knows IQM. `PhysicalChip` declares `fetch`/`load` as stubs that chip classes override.
  - `chips/__init__.py`: `CHIPS` (layout chip name -> class), `load_chip(name, snapshot, root)`, re-exports `snapshots`, `CACHE_ROOT`. `chips/__main__.py`: the fetch CLI (prints a clean error on HTTP failure or unexpected API data).
  - `vm.py`: `Node`, `Category(name, graph)`, `VM(name, category, graph)` (`VM.build`, `VM.connectors`), `connector_number`, `labels`.
  - `virtual_topology.py`: `VirtualTopology(basis_gates, categories, vms)` with `category(name)`, `vm(name)`, `vms_of`, `canonical_vms`, `graph(category=|vms=)`, `target(...)`, `fusion_candidates(n)`, `interconnect`, `validate`; module functions `fuse` (-> `FusedGraph`), `fusion_candidates`, `topology_from_dicts`, `target`.
  - `chip_layout.py`: `ChipLayout(physical_chip, virtual_topology, mapping)`, `whole_chip(chip)` (default: one category "chip" + one VM "chip" = active qubits/couplers, node i = `chip.active_qubits[i]`), `from_file`/`from_dict` (hand-written cut). The layout dict/JSON names `"chip"` and optionally `"snapshot"` (default `"latest"`); `basis_gates` come from the chip, not from the file. `check()` runs at construction.
  - `jobs.py`: `JobState` (StrEnum), `Job` (carries `status`, `counts`, `error`), `Decision`, `PlacedJob`, `Batch`.
- `steps/` — each step turns one representation into the next, in the order of a job's path:
  - `validation.py`: `check_circuit(circuit, graph, basis_gates)`.
  - `scheduler.py`: `Scheduler` (HyperQ pass 1) -> decisions `(Job, vms)`.
  - `mapping.py`: `Mapper` -> `Batch` of `PlacedJob` (physical qubits).
  - `executor.py`: `Executor(backend=None, seed=None)` (Aer by default): `combine` (composite circuit), `execute` (counts per job).
- `hypervisor.py`: `Hypervisor(chip_layout, executor=None, interval=0.5)`. `chip_layout` is a `PhysicalChip` (-> `ChipLayout.whole_chip`), a `ChipLayout` or a JSON path (relative paths resolved against `PROJECT_ROOT`). The constructor starts a daemon thread running the queue every `interval` s; `stop()` stops it and drains the queue (idempotent, also called by `with Hypervisor(...) as hv:`); `submit` after `stop()` raises `RuntimeError`. Attributes `chip_layout`, `virtual_topology`, `jobs` ({id: Job}), `queue`, `history`, `scheduler`, `mapper`, `executor`. Methods `submit`, `job`, `status`, `result(job_id, timeout=None)` (always waits; `TimeoutError`, `RuntimeError` if the job failed or the thread died), `stop`. No synchronous mode, no public `run_queue`. Any object with `execute(batch, shots)` can replace the executor.

`ultraq_qiskit_connector/`: `UltraqProvider(hv)` (`backends`, `get_backend(name | vms=)`, `fusion_candidates`), `CategoryBackend`, `FusedBackend`, `UltraqJob`. Only uses a `Hypervisor` object (`submit`, `status`, `result`, `virtual_topology`).

`examples/demo.py`: fetches Garnet, cuts two S4 VMs in code (vm1 = QB1 QB2 QB4 QB5, vm2 = QB6 QB7 QB11 QB12), alice and bob GHZ-4 share one batch. No layout JSON file is shipped. `calibration_data/<qpu>/<timestamp>/`: snapshot cache, gitignored (not versioned).

## Rules

- Nothing IQM-specific outside `ultraq_backend/model/chips/iqm.py` (`chips/__init__.py` only registers the classes in `CHIPS`): `grep -rniE "iqm|prx" ultraq_backend ultraq_qiskit_connector --include=*.py | grep -v "model/chips/iqm.py\|model/chips/__init__.py"` must find nothing but docstring examples.
- The calibration snapshot is the source of truth for the chip: no hand-written chip description. Inactive qubits and couplers stay in the graph (stable indices from one snapshot to the next); a layout is valid for its snapshot only.
- The scheduler does not know physical qubits: it only sees the `VirtualTopology` and only produces decisions `(Job, vms)`.
- The mapping does not modify circuits. Only `executor.py` builds the composite circuit and talks to a backend.
- Qiskit gate names everywhere (`r`, `cz`); the vendor -> Qiskit translation is `PhysicalChip.native_gates`, filled by the chip module (`iqm.GATES`) and applied only by `PhysicalChip.qiskit_basis_gates`.

## Model invariants

- A connector number is in **exactly 2** VMs (= one physical qubit) and is usable only in a fusion of those 2 VMs.
- A VM graph = its category graph (same indices), then its connectors sorted by number.
- A fused group is always in canonical (declaration) order (`VirtualTopology.canonical_vms`): `fuse`, `submit`, `FusedBackend` (name `ultraq_vm1+vm4`) and `job.request` ignore the order given. `fuse` is deterministic (VMs in declaration order, then node order; a merged connector gets the index of its first occurrence); `fuse(topo, [vm])` has the shape of the category.
- The interconnect graph is computed (`VirtualTopology.interconnect()`), never stored.
- `ChipLayout.check` rejects: basis gates different from the chip's, unmapped or unknown labels, a physical qubit used by two nodes, a connector mapped to two qubits, an inactive qubit, a VM edge that is not a coupler or is an inactive coupler.
- Category job: the hypervisor picks the VM. Fused job: its VMs are fixed, it waits until all are free.
- A circuit is checked once (`check_circuit` in `Hypervisor.submit`, also reached through `backend.run`).
- The result does not reveal the VM used; only `hv.history` records it.
- A batch only mixes jobs with the same number of shots; one batch runs at a time.
- A failing job (scheduler, mapper or executor exception, never placeable) goes to `ERROR` with its cause in `job.error`; `hv.result` raises `RuntimeError`, `UltraqJob.result` raises `JobError`. The run loop never raises because of a job.

## Conventions

- **Undirected** `rustworkx.PyGraph` graphs, compact indices `0..n-1`, nodes `Node(kind, label)`. Circuit qubit `i` = node `i`.
- Counts of a job: all its bits, bit 0 rightmost, no spaces; the composite counts are split by register name `job{i}_c`.
- Module docstring: role + what the module must not know. Every public API documented.
- Code and docstrings in English.
