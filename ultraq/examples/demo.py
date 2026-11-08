"""Demo: two users run GHZ-4 jobs on a tiny cut of IQM Garnet; both jobs share one batch.

Fetches the current Garnet calibration (IQM_TOKEN in the environment or in `.env`),
cuts two 2x2 squares out of the chip and runs the jobs on Aer.

Run from the project root: uv run python examples/demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qiskit import QuantumCircuit, transpile

from ultraq_backend import Hypervisor
from ultraq_backend.model.chip_layout import ChipLayout
from ultraq_backend.model.chips import IQMGarnet
from ultraq_qiskit_connector import UltraqProvider

chip = IQMGarnet.fetch()
print(f"{chip.name} snapshot {chip.snapshot}")

# One category "S4" (2x2 square), two VMs of it: vm1 on QB1 QB2 QB4 QB5, vm2 on QB6 QB7 QB11 QB12.
layout = ChipLayout.from_dict({
    "chip": "garnet",
    "snapshot": chip.snapshot,
    "categories": [{"name": "S4", "qubits": ["q0", "q1", "q2", "q3"],
                    "edges": [["q0", "q1"], ["q0", "q2"], ["q1", "q3"], ["q2", "q3"]]}],
    "vms": [{"name": "vm1", "category": "S4", "connectors": {}},
            {"name": "vm2", "category": "S4", "connectors": {}}],
    "mapping": {"vm1": {"q0": 0, "q1": 1, "q2": 3, "q3": 4},
                "vm2": {"q0": 5, "q1": 6, "q2": 10, "q3": 11}},
})

ghz = QuantumCircuit(4, 4)
ghz.h(0)
for i in range(3):
    ghz.cx(i, i + 1)
ghz.measure(range(4), range(4))

with Hypervisor(layout) as hv:
    backend = UltraqProvider(hv).get_backend("S4")
    circuit = transpile(ghz, backend, seed_transpiler=1)
    jobs = {user: backend.run(circuit, shots=1000) for user in ("alice", "bob")}
    for user, job in jobs.items():
        print(f"{user}: {job.result().get_counts()}")

print(f"history: {hv.history}")
