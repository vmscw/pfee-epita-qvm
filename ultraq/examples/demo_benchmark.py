"""Small benchmark of ultraq on the real IQM Garnet chip, with its default layout.

Default Garnet layout (`ultraq_backend/model/chips/default_layout/default_iqm_garnet.json`):
4 VMs vm1..vm4 of one category S4 (2×2 square), linked in a ring by 4
connectors (QB3, QB10, QB17, QB18).

Three runs of GHZ circuits, each printing the share of ideal outcomes
(all 0 or all 1):

    1. one circuit on S4;
    2. two circuits at the same time on S4 (two VMs, one composite circuit);
    3. one circuit on the fusion vm1 + vm2 (9 qubits, through connector QB3).

Needs IQM_URL, IQM_CALIBRATION_TOKEN and IQM_TOKEN (environment or .env).
From the project root `ultraq/`:

    uv run python examples/demo_benchmark.py
"""

from qiskit import QuantumCircuit, transpile

from ultraq_backend import ChipLayout, Hypervisor
from ultraq_backend.model.chips import IQMGarnet
from ultraq_backend.steps.executor import IQMExecutor
from ultraq_qiskit_connector import UltraqProvider


def ghz(n: int) -> QuantumCircuit:
    """n-qubit GHZ state: ideally half 00...0, half 11...1."""
    qc = QuantumCircuit(n, n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.measure(range(n), range(n))
    return qc


def report(name: str, counts: dict[str, int]) -> None:
    n = len(next(iter(counts)))
    ideal = counts.get("0" * n, 0) + counts.get("1" * n, 0)
    print(f"{name}: GHZ {n} qubits, {ideal / sum(counts.values()):.1%} ideal outcomes")


IQMGarnet.fetch()  # fresh calibration, cached: the layout below loads it ("latest")
layout = ChipLayout.from_file("ultraq_backend/model/chips/default_layout/default_iqm_garnet.json")

executor = IQMExecutor(layout.physical_chip)  # one connection to the chip, shared by the hypervisors below

# Demo 1 — reference: one circuit alone on one VM of category S4 (the
# hypervisor picks a free VM); its quality is the baseline for demo 2.
with Hypervisor(layout, executor=executor) as hv:
    s4 = UltraqProvider(hv).get_backend("S4")
    print("1. one circuit on S4")
    report("S4", s4.run(transpile(ghz(4), s4), shots=1000).result().get_counts())

# Demo 2 — multiprogramming: two circuits from two "users" run at the same time
# on two different VMs, combined into one circuit on the chip, each getting its
# own counts back. This hypervisor runs its queue every 2 s instead of 0.5 s,
# so the two jobs, submitted one after the other, end up in the same batch.
with Hypervisor(layout, executor=executor, interval=2) as hv:
    s4 = UltraqProvider(hv).get_backend("S4")
    print("2. two circuits in parallel on S4")
    job_a = s4.run(transpile(ghz(4), s4), shots=1000)
    job_b = s4.run(transpile(ghz(3), s4), shots=1000)
    report("S4 (a)", job_a.result().get_counts())
    report("S4 (b)", job_b.result().get_counts())

# Demo 3 — fusion: a circuit too big for one VM (9 qubits) runs on vm1 + vm2
# fused through their shared connector QB3 (4 + 4 + 1 qubits).
with Hypervisor(layout, executor=executor) as hv:
    fused = UltraqProvider(hv).get_backend(vms=["vm1", "vm2"])
    print("3. one circuit on the fusion vm1 + vm2")
    report("vm1+vm2", fused.run(transpile(ghz(9), fused), shots=1000).result().get_counts())
