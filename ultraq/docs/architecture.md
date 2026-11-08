# Architecture

How the code is organised, what each part may know, and the path of one job. The model itself (categories, VMs, connectors, fusion) is in [model.md](model.md), the calibration in [calibration.md](calibration.md), usage in [guide.md](guide.md).

Everything runs **in one process**, the user's: no server, no serialisation. The only network access is fetching a calibration snapshot.

## Layers

- **Physics**: `PhysicalChip` (`model/chips/`): qubits, couplers, native gates and calibration of one snapshot.
- **Virtual layer**: `VirtualTopology` (`model/virtual_topology.py`, bricks in `model/vm.py`): categories (VM shapes) and VMs.
- **Link**: `ChipLayout` (`model/chip_layout.py`): chip + topology + `mapping` `{vm: {label: physical qubit}}`, checked at construction. Default: `ChipLayout.whole_chip(chip)`, the whole chip as one VM.
- **Processing**: `steps/`: validation -> scheduler -> mapping -> executor, chained by the `Hypervisor`.

## Packages and dependency rules

```
ultraq_qiskit_connector/     UltraqProvider -> CategoryBackend / FusedBackend -> UltraqJob
        │  uses only: hv.virtual_topology, hv.submit, hv.status, hv.result
        ▼
ultraq_backend/
  hypervisor.py              Hypervisor: jobs, queue, history, background thread
        │ chains
        ▼
  steps/                     validation.check_circuit, Scheduler, Mapper, Executor
        │ import
        ▼
  model/                     chips/, vm.py, virtual_topology.py, chip_layout.py, jobs.py
```

- `model/` never imports `steps/` nor `hypervisor.py`. `chip_layout.py` is the only model module that imports both `chips/` and `virtual_topology.py`.
- The steps never import each other; only the `Hypervisor` knows all four.
- `ultraq_backend` never imports `ultraq_qiskit_connector`. The connector imports `Hypervisor` for type hints only.
- `model/chips/iqm.py` is the only IQM-aware module; it translates IQM gate names to Qiskit names (`prx` -> `r`). Everywhere else: Qiskit names (`["r", "cz"]` on Garnet).
- `steps/executor.py` is the only module that talks to a simulator (Aer by default).

## Path of a job

1. **Target.** `provider.get_backend("S4")` (or `get_backend(vms=[...])` for a fusion) asks `hv.virtual_topology.target(...)` for the Qiskit `Target` of the category graph (or fused graph).
2. **Transpile.** The user runs `transpile(qc, backend)`. Circuit qubit `i` = node `i` of that graph.
3. **Submit.** `backend.run(qc)` calls `hv.submit`, which checks the circuit (`check_circuit`: size, native gates, 2-qubit gates on edges, at least one measure) and queues a `Job` in state `QUEUED`. A circuit that was not transpiled is refused with a `ValueError`.
4. **Schedule.** The background thread wakes up every `interval` seconds and empties the queue batch by batch. The `Scheduler` (HyperQ pass 1) tries jobs in queue order: a category job takes the first free VM of its category, a fused job needs all its VMs free; a job that does not fit waits and later jobs may pass it. A batch only mixes jobs with the same shots.
5. **Map.** The `Mapper` turns each `(job, vms)` into physical qubits via `fuse(...).origins` and `ChipLayout.mapping`. Circuits are not modified.
6. **Execute.** The `Executor` builds one composite circuit (one classical register `job{i}_c` per job), runs it on Aer, and splits the counts per job.
7. **Result.** `job.result()` waits for the job and returns a standard `qiskit.result.Result`. The VM used is not revealed; `hv.history` records it per batch.

If the scheduler, the mapper or the executor raises, the affected jobs go to `ERROR` with the cause in `job.error` (`hv.result` raises `RuntimeError`, `UltraqJob.result` raises `JobError`); the loop goes on. Jobs that can never be placed (e.g. a category without VM) also go to `ERROR`.

## The background thread

`Hypervisor(...)` starts a daemon thread at construction; there is no synchronous mode. Jobs submitted within the same `interval` (default 0.5 s) can share a batch. `stop()` stops the thread and runs what is left, so no job stays `QUEUED`; it is idempotent and called when leaving a `with Hypervisor(...) as hv:` block. After `stop()`, `submit` raises `RuntimeError`.

`result(job_id, timeout=None)` always waits; it raises `TimeoutError` after `timeout` seconds, and `RuntimeError` if the thread died.

Locks: an `RLock` (with a `Condition` that wakes `result()`) protects `jobs`, `queue`, `history` and job states; a second lock makes sure only one batch runs at a time. Execution happens outside the state lock, so `submit` is never blocked.

## Link with HyperQ

**Taken:** pass 1 of the scheduler (spatial placement, jobs may pass a blocked one), compilation on the VM shape, one composite circuit with one register per job, counts split per job, a library behind a standard Qiskit interface.

**Generalised:** several categories of arbitrary shape (HyperQ: one 3x3 grid), fusion of any connected group of VMs through connectors (HyperQ: rectangles), a chip built from a real calibration snapshot.

**Not taken:** the temporal pass (reset and reuse), the intra-VM pass, noise-aware placement, dynamic circuits, gate direction. See [extending.md](extending.md).
