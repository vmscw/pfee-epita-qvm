# Extending the project

Possible next steps, not decisions. Module map: [architecture.md](architecture.md);
chip model: [calibration.md](calibration.md).

## Adding a chip

One `PhysicalChip` subclass per chip; duplication between chip classes is accepted.

- **Another IQM QPU**: copy `IQMGarnet` in `ultraq_backend/model/chips/iqm.py`, change the
  QPU name, id and display name, add it to `CHIPS` in `chips/__init__.py`.
- **Another vendor**: a new module (e.g. `chips/ibm.py`), the only one to know that vendor,
  with a dataclass subclass of `PhysicalChip` that overrides `fetch(...)` (vendor API ->
  cache -> chip) and `load(snapshot="latest", root=...)` (cache -> chip, no network), fills
  the generic fields (`native_gates` as `{vendor name: standard Qiskit name}`,
  `symmetric_gates`, `graph` of `Qubit`/`Coupler` with their `active` flag), then an entry
  in `CHIPS`. Native gates must be standard Qiskit gates on 1 or 2 qubits.

## Directed gates

VM graphs and checks are undirected; only `PhysicalChip.coupling_map()` and `target()`
honour direction for a gate outside `symmetric_gates`. A directed gate (IBM `ecr`) would
need directed VM graphs, or a direction fix in the executor. Not needed for IQM (`cz`).

## Using the calibration data

Today the calibration only decides which qubits and couplers are active.

- **Noise model**: build an Aer `NoiseModel` from `chip.target()` (gate errors), T1/T2
  and the `measure` fidelity, and pass `Executor(AerSimulator(noise_model=...))`. The
  composite circuit is already on physical qubits.
- **Noise-aware placement** (HyperQ's `get_qvm_ranking`): a score per VM name, computed
  outside the scheduler from the `ChipLayout`, used by `Scheduler.place` instead of
  declaration order.

## Real hardware

`Executor(backend=...)` takes any Qiskit backend whose `run(circuit, shots=...)` accepts
the composite circuit as-is; `Hypervisor(executor=...)` takes any object with
`execute(batch, shots)`. Real hardware would likely need the composite transpiled for the
real backend and the provider's queue handled.

## More HyperQ passes

`Scheduler` implements pass 1 (spatial) only. Missing: the intra-VM pass, the temporal
pass (VM reuse with reset). Contract of a pass: input = the queue in arrival order (all
VMs free); output = decisions `(Job, vms)` of the next batch + remaining jobs; a category
job gets one VM of its category, a fused job exactly its VMs; no shared VM and same shots
in a batch; no decision on a non-empty queue = never placeable (jobs go to `ERROR`).
Intra-VM and temporal passes would need a richer `Decision`, `Mapper` and `PlacedJob`.

## Offline reference snapshot

`calibration_data/` is gitignored, so a fresh clone needs a token and a fetch, and results
depend on the day's calibration. Versioning one snapshot (Garnet is about 1.8 MB), loaded
with `root=`, would make the demo offline and reproducible.

## Other ideas

- **Larger fusions**: `fusion_candidates` enumerates every combination (exponential);
  Emerald-sized layouts need a bounded search.
- **Mixed shots in a batch**: run the maximum and subsample.
- **Concurrent batches**: one batch runs at a time; overlapping batches on disjoint VMs
  would need finer locking of the hypervisor state.
