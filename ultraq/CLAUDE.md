# CLAUDE.md — ultraq

qVM multiprogramming inspired by HyperQ (OSDI'25), in a single process: a physical chip (IQM Garnet or Emerald, built from a fetched calibration snapshot) is cut into VMs; a `Hypervisor` queues circuits, places them on free VMs, maps them to physical qubits and runs them together on Aer or, as-is, on the real IQM chip (iqm-client). A separate package exposes all this as plain Qiskit (provider, virtual backends). Documentation: `README.md`.

Keep the code simple: no abstract class, registry or extension point until there are two implementations.

## Commands

From the project root `ultraq/` (ignore uv's `VIRTUAL_ENV` warning):

```bash
uv sync                      # includes iqm-client 36 (real IQM runs), which pins qiskit < 2.2
uv run python -m ultraq_backend.model.chips garnet [--set default] [--out DIR]   # fetch + cache a snapshot (IQM_URL, IQM_CALIBRATION_TOKEN in env or .env)
```

Never read `.env` (it holds the IQM tokens). Environment variables (all from `.env` at the repository root, listed in `.env.example`): `IQM_URL` (Resonance server, no URL in the code), `IQM_CALIBRATION_TOKEN` (fetching calibration) and `IQM_TOKEN` (running circuits; name imposed by iqm-client, which reads it itself and refuses a `token=` argument when it is set), `ULTRAQ_LOG_LEVEL` (DEBUG, INFO, WARNING or ERROR, default INFO). Tokens and the URL are never function arguments.

There is no demo or example script: check changes offline with a scratch script loading a cached snapshot (`IQMGarnet.load(root=...)`), on `AerExecutor()` or on a scratch `Executor` subclass whose `make_backend` returns `IQMFakeGarnet()` (`iqm.qiskit_iqm.fake_backends.fake_garnet`).

## Map

Two packages. `ultraq_backend/` is the core and never imports `ultraq_qiskit_connector/`; inside the core, `model/` never imports `steps/`.

`ultraq_backend/`:

- `model/` — data only, no execution logic.
  - `chips/physical_chip.py`: `PhysicalChip`, `Qubit`, `Coupler`, `RawMetric`. Vendor-agnostic: coupling graph (node = `Qubit`, edge = `Coupler`), `active_qubits`, `active_couplers`, `qiskit_basis_gates`, `coupling_map`, `target` (with calibration errors).
  - `chips/iqm.py`: `IQMGarnet`, `IQMEmerald` (`fetch()` from the IQM Resonance API + cache, `load(snapshot)` from the cache, no network), `snapshots`, `CACHE_ROOT`. The only model module that knows IQM; it describes the chip, it never runs circuits. `PhysicalChip` declares `fetch`/`load` as stubs that chip classes override.
  - `chips/__init__.py`: `CHIPS` (layout chip name -> class), `load_chip(name, snapshot, root)`, re-exports `snapshots`, `CACHE_ROOT`. `chips/__main__.py`: the fetch CLI (prints a clean error on HTTP failure or unexpected API data).
  - `vm.py`: `Node`, `Category(name, graph)`, `VM(name, category, graph)` (`VM.build`, `VM.connectors`), `connector_number`, `labels`.
  - `virtual_topology.py`: `VirtualTopology(basis_gates, categories, vms)` with `category(name)`, `vm(name)`, `vms_of`, `canonical_vms`, `graph(category=|vms=)`, `target(...)`, `fusion_candidates(n)`, `interconnect`, `validate`; module functions `fuse` (-> `FusedGraph`), `fusion_candidates`, `topology_from_dicts`, `target`.
  - `chip_layout.py`: `ChipLayout(physical_chip, virtual_topology, mapping)`, `whole_chip(chip)` (default: one category "chip" + one VM "chip" = active qubits/couplers, node i = `chip.active_qubits[i]`), `from_file`/`from_dict` (hand-written cut). The layout dict/JSON names `"chip"` and optionally `"snapshot"` (default `"latest"`); `basis_gates` come from the chip, not from the file. `check()` runs at construction.
  - `jobs.py`: `JobState` (StrEnum), `Job` (carries `status`, `counts`, `error`), `Decision`, `PlacedJob`, `Batch`.
- `steps/` — each step turns one representation into the next, in the order of a job's path:
  - `validation.py`: `check_circuit(circuit, graph, basis_gates)`.
  - `scheduler.py`: `Scheduler` (HyperQ pass 1) -> decisions `(Job, vms)`.
  - `mapping.py`: `Mapper` -> `Batch` of `PlacedJob` (physical qubits).
  - `executor/` (package, re-exports everything below):
    - `executor.py`: `Executor(run_options=None, result_options=None)`, abstract: subclasses only implement `make_backend()` (the Qiskit backend, created once by `__init__`, must run circuits as-is). `combine` (composite circuit), `execute` (counts per job; [] for an empty batch; RuntimeError on a failed result; blocks until the backend returns), `failure_reason` (hook), `job_ids` (backend job id per batch); `split_counts` (missing never-measured registers read as zeros).
    - `aer.py`: `AerExecutor(run_options=None, result_options=None)` (`AerSimulator()`, the hypervisor's default).
    - `iqm.py`: `IQMExecutor(chip, run_options=None, result_options=None)` (`make_backend` = iqm-client `IQMBackend`, no server-side transpilation, the snapshot's calibration set pinned; lazy import of iqm-client; keeps `chip`; `failure_reason` = `job.error_message()`), checks `IQM_TOKEN` (read by iqm-client itself), `check_qubit_order`. The chip is the hardware description, the executor is the execution target: they stay separate.
- `env.py`: `from_env(name, what)`: environment variable `name`, `.env` (at or above the cwd) loaded first; RuntimeError naming `what` if not set. Knows no variable name: callers pass it (`IQM_URL`, `IQM_CALIBRATION_TOKEN`, `IQM_TOKEN`).
- `log.py`: `setup_logging()`, run once at import of `ultraq_backend` (and of `ultraq_qiskit_connector`): level `ULTRAQ_LOG_LEVEL` for the loggers `ultraq_backend` and `ultraq_qiskit_connector` only (console handler, `propagate=False`); the root logger and the libraries are never configured.
- `hypervisor.py`: `Hypervisor(chip_layout, executor=None, interval=0.5)`. `chip_layout` is a `PhysicalChip` (-> `ChipLayout.whole_chip`), a `ChipLayout` or a JSON path (a relative path is relative to the current directory). The constructor starts a daemon thread running the queue every `interval` s; `stop()` stops it and drains the queue (idempotent, also called by `with Hypervisor(...) as hv:`); `submit` after `stop()` raises `RuntimeError`. Attributes `chip_layout`, `virtual_topology`, `jobs` ({id: Job}), `queue`, `history`, `scheduler`, `mapper`, `executor`. Methods `submit`, `job`, `status`, `result(job_id, timeout=None)` (always waits; `TimeoutError`, `RuntimeError` if the job failed or the thread died), `stop`. No synchronous mode, no public `run_queue`. `executor` is any `Executor` (default `AerExecutor()`).

`ultraq_qiskit_connector/`: `UltraqProvider(hv)` (`backends`, `get_backend(name | vms=)`, `fusion_candidates`), `CategoryBackend`, `FusedBackend`, `UltraqJob`. Only uses a `Hypervisor` object (`submit`, `status`, `result`, `virtual_topology`).

No layout JSON file is shipped. `calibration_data/<qpu>/<timestamp>/`: snapshot cache, gitignored (not versioned).

## Rules

- Nothing IQM-specific outside `ultraq_backend/model/chips/iqm.py` (calibration) and `ultraq_backend/steps/executor/iqm.py` (execution target); `chips/__init__.py` only registers the classes in `CHIPS`, `steps/executor/__init__.py` only re-exports: `grep -rniE "iqm|prx" ultraq_backend ultraq_qiskit_connector --include=*.py | grep -v "model/chips/iqm.py\|model/chips/__init__.py\|steps/executor/iqm.py\|steps/executor/__init__.py"` must find nothing but docstring examples.
- The calibration snapshot is the source of truth for the chip: no hand-written chip description. Inactive qubits and couplers stay in the graph (stable indices from one snapshot to the next); a layout is valid for its snapshot only.
- The scheduler does not know physical qubits: it only sees the `VirtualTopology` and only produces decisions `(Job, vms)`.
- The mapping does not modify circuits. Only `steps/executor/executor.py` builds the composite circuit and talks to a backend.
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

- Logging: `log = logging.getLogger(__name__)` in each module, lazy %-formatting. DEBUG = details (decisions, mapping, composite circuit, HTTP paths), INFO = life cycle (hypervisor start/stop, job submitted/done, batch and its duration, backend job id, calibration fetched/loaded, layout built), WARNING = anomalies that do not fail (missing metrics), ERROR = failures, traceback logged once where caught (hypervisor). Never log a token, a header or any `.env` value (not even `IQM_URL`: log paths relative to the server). Short job ids (`job_id[:8]`). `warnings.warn` only for API misuse (connector run options); CLI output stays `print`.

- **Undirected** `rustworkx.PyGraph` graphs, compact indices `0..n-1`, nodes `Node(kind, label)`. Circuit qubit `i` = node `i`.
- Counts of a job: all its bits, bit 0 rightmost, no spaces; the composite counts are split by register name `job{i}_c`.
- Module docstring: role + what the module must not know. Every public API documented.
- Code and docstrings in English.
