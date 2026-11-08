# IQM calibration data and the physical chip

A chip (IQM Garnet, IQM Emerald) is never described by hand: it is built from a
calibration snapshot fetched from the IQM Resonance REST API. **The snapshot is the
source of truth**: qubits, couplers, which of them are active and every calibration value
come from it.

Everything lives in `ultraq_backend/model/chips/`:

| File | Role |
|---|---|
| `physical_chip.py` | vendor-agnostic model: `PhysicalChip`, `Qubit`, `Coupler`, `RawMetric`; `PhysicalChip.fetch`/`load` are stubs that chip classes override |
| `iqm.py` | the only module that knows IQM: HTTP calls, cache, parsing, `IQMGarnet`, `IQMEmerald`, `snapshots` |
| `__init__.py` | `CHIPS` (name -> class), `load_chip`, re-exports `snapshots` and `CACHE_ROOT` |
| `__main__.py` | the fetch command line |

## Token

Taken from the `token=` argument of `fetch`, else from the `IQM_TOKEN` environment
variable (a `.env` file in the current directory or a parent is loaded first). Never
commit `.env`. The token only goes into the HTTP header: it never appears in error
messages, cached files or CLI output.

<!-- no-test -->
```bash
export IQM_TOKEN=...            # or a line IQM_TOKEN=... in .env
```

## Fetching

From the project root:

<!-- no-test -->
```bash
uv run python -m ultraq_backend.model.chips garnet                 # default calibration set
uv run python -m ultraq_backend.model.chips emerald --set <id> --out calibration_data
```

```text
IQM Garnet snapshot 20261108T115135Z (calibration set f8d73b3f-96ed-4cdd-948e-e598224fddf8)
  20 qubits (19 active, inactive: ['QB14']), 30 couplers (26 active)
```

On failure (missing token, HTTP error, network, timeout, non-JSON body, or API data the
parser does not expect), it prints `error: ...` on stderr, without traceback, and exits
with code 1. From Python: `IQMGarnet.fetch(calibration_set="default", token=None,
root=CACHE_ROOT, timeout=30.0)` (same for `IQMEmerald`), which raises `RuntimeError` on
HTTP or network failure.

Three `GET` calls on `https://resonance.iqm.tech/api/v1/calibration-sets/<qpu>/<set>`
(`<set>` = an id or `default`), with an explicit `User-Agent: ultraq/0.1` (the API firewall
answers 403 to urllib's default one):

| Endpoint | Cached file |
|---|---|
| `.../<set>` | `calibration_set.json` |
| `.../<set>/metrics` | `metrics.json` (a 404 only warns; `meta.json` then says `"has_metrics": false`) |
| `.../<set>/dynamic-quantum-architecture` | `dynamic_quantum_architecture.json` |

## Cache

Each fetch writes a new directory `<root>/<qpu>/<UTC timestamp>/` with the three raw
responses and a `meta.json` (`qpu`, `requested_set`, `fetched_at`, `has_metrics`). The
default root `CACHE_ROOT` is `calibration_data/` at the project root, whatever the current
directory; it is gitignored, so a fresh clone must fetch once. A snapshot is named by its
timestamp; `"latest"` is the most recent one.

```python
from ultraq_backend.model.chips import CHIPS, IQMGarnet, load_chip, snapshots

print(sorted(CHIPS), snapshots("garnet"))       # ['emerald', 'garnet'] ['20261108T115135Z']
chip = IQMGarnet.load()                         # latest snapshot, no network
same = load_chip("garnet", chip.snapshot)       # by name and timestamp
print(chip.snapshot, chip.calibration_set_id)   # 20261108T115135Z f8d73b3f-96ed-4cdd-948e-e598224fddf8
```

`load(snapshot="latest", root=CACHE_ROOT)` and `load_chip(name, snapshot, root)` raise
`FileNotFoundError` when nothing is cached (the message gives the fetch command);
`load_chip` raises `KeyError` for a name not in `CHIPS`.

## From snapshot to chip

`chip.graph` is a `rustworkx.PyGraph`: node `i` is physical qubit `i` (`Qubit`), each
edge a physical coupler (`Coupler`). Inactive qubits and couplers **stay in the graph**,
so indices are stable from one snapshot to the next.

- **Qubits**: the DQA `qubits` in order (`QB1` -> 0). Active if the DQA offers both
  `prx` and `measure` on it.
- **Couplers**: every `cz` locus of the DQA plus every `TC-a-b` label of the calibration
  set. Active if the DQA offers `cz` on it.
- **Raw values**: every observation of both files is kept as a `RawMetric(name, value,
  unit, source, extra)`, attached to its coupler, else its qubit, else the chip.
- **Typed values** (from `metrics.json`, invalid observations skipped): `Qubit.t1`,
  `Qubit.t2` (seconds, Ramsey), `Qubit.gate_fidelity["r"]` and `["measure"]`,
  `Coupler.gate_fidelity["cz"]`.
- **Gates**: `native_gates = {"prx": "r", "cz": "cz"}` (IQM -> Qiskit),
  `symmetric_gates = {"cz"}`. IQM-only fields: `calibration_set_id`, `gate_loci` (the raw
  DQA); generic code never reads them.

```python
q = chip.qubit(chip.index("QB1"))
print(q.label, q.active, q.t1, q.gate_fidelity)
# QB1 True 1.6037357837543914e-05 {'measure': 0.953, 'r': 0.9974995330472946}
print(chip.coupler(0, 1).gate_fidelity)         # {'cz': 0.9916367445830574}
print([chip.qubit(i).label for i in range(chip.num_qubits) if not chip.qubit(i).active])   # ['QB14']
```

## Qiskit view

- `chip.qiskit_basis_gates()` -> `['r', 'cz', 'measure']`;
- `chip.coupling_map()`: active couplers, both directions (every 2-qubit gate is symmetric);
- `chip.target()`: the active part of the chip with `error = 1 - fidelity` and T1/T2.

```python
target = chip.target()
print(sorted(target.operation_names), target["cz"][(0, 1)].error)
# ['cz', 'measure', 'r'] 0.008363255416942605
```

These values are not used by the scheduling or the simulation yet (see [extending.md](extending.md)).

## Use by the layouts

`Hypervisor(chip)` uses `ChipLayout.whole_chip(chip)`: the active qubits and couplers as
one VM. A hand-written cut names its chip and optionally its snapshot
(`{"chip": "garnet", "snapshot": "20261108T115135Z", ...}`, default `"latest"`) and is
rejected if a node is on an inactive qubit or an edge on a missing or inactive coupler: a
cut is valid for its snapshot only. See [guide.md](guide.md#2-cutting-the-chip-into-vms).
