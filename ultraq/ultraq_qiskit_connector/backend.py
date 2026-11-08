"""Virtual Qiskit backends (BackendV2) on top of a `Hypervisor`.

- `CategoryBackend`: one per category (case 1: the circuit fits in a
  category). The hypervisor chooses the VM.
- `FusedBackend`: a group of VMs fused into one graph (case 2: the circuit is
  too big for every category). The job runs on exactly these VMs.

Both expose the `target` of their graph, so `transpile(qc, backend)` works,
then `backend.run(qc)` checks the circuit, queues it in the hypervisor and
returns an `UltraqJob`.

This module must not know physical qubits, the scheduling policy, the
execution target nor any vendor.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import rustworkx as rx
from qiskit import QuantumCircuit
from qiskit.providers import BackendV2, Options
from qiskit.transpiler import Target

from ultraq_qiskit_connector.job import UltraqJob

if TYPE_CHECKING:
    from ultraq_backend.hypervisor import Hypervisor

_IGNORED_OPTIONS = {"seed_simulator"}  # passed by BackendSamplerV2; meaningless here


class _UltraqBackend(BackendV2):
    """Common part: the hypervisor and the job request ({"category": ...} or
    {"vms": [...]}); graph and target come from the hypervisor."""

    def __init__(
        self,
        name: str,
        hypervisor: Hypervisor,
        request: dict[str, Any],
        provider: Any = None,
    ) -> None:
        super().__init__(provider=provider, name=name, backend_version="0.1")
        self._hypervisor = hypervisor
        self._request = request
        self._graph = hypervisor.virtual_topology.graph(**request)
        self._target = hypervisor.virtual_topology.target(**request)

    @property
    def target(self) -> Target:
        """Qiskit Target of the backend graph (basis gates, graph edges)."""
        return self._target

    @property
    def max_circuits(self) -> int:
        """One circuit per job (`run` rejects a list of several circuits)."""
        return 1

    @property
    def graph(self) -> rx.PyGraph:
        """The graph circuits are compiled on: circuit qubit i = node i."""
        return self._graph

    @classmethod
    def _default_options(cls) -> Options:
        return Options(shots=1024, memory=False)

    def run(self, run_input: QuantumCircuit | list[QuantumCircuit], **options: Any) -> UltraqJob:
        """Queue one transpiled circuit in the hypervisor and return its job.

        `run_input`: a QuantumCircuit or a list holding exactly one.
        Options: `shots` (default 1024), `memory` (per-shot results).
        Raises ValueError (from `Hypervisor.submit`, which checks the circuit
        and the shots) if the circuit does not fit the backend: transpile it
        first with `transpile(qc, backend)`.
        """
        circuit = _single_circuit(run_input)
        unknown = set(options) - set(self.options) - _IGNORED_OPTIONS
        if unknown:
            warnings.warn(f"{self.name}: ignoring unknown run options {sorted(unknown)}")
        shots = options.get("shots", self.options.shots)
        memory = bool(options.get("memory", self.options.memory))

        job_id = self._hypervisor.submit(circuit, shots=shots, **self._request)
        header = {
            "name": circuit.name,
            "creg_sizes": [[creg.name, creg.size] for creg in circuit.cregs],
            "memory_slots": circuit.num_clbits,
        }
        return UltraqJob(self, job_id, self._hypervisor, header, shots, memory)


class CategoryBackend(_UltraqBackend):
    """Backend of one category: the hypervisor picks a free VM of that category."""

    def __init__(self, category: str, hypervisor: Hypervisor, provider: Any = None) -> None:
        super().__init__(f"ultraq_{category}", hypervisor, {"category": category}, provider)
        self.category = category


class FusedBackend(_UltraqBackend):
    """Backend of a fused group of VMs: the job waits until they are all free.

    The group is kept in declaration order whatever the order given (e.g.
    vms=["vm4", "vm1"] -> name "ultraq_vm1+vm4", `vms` ["vm1", "vm4"]), so
    the target and the placement always match.
    """

    def __init__(self, vms: list[str], hypervisor: Hypervisor, provider: Any = None) -> None:
        vms = hypervisor.virtual_topology.canonical_vms(vms)
        super().__init__("ultraq_" + "+".join(vms), hypervisor, {"vms": list(vms)}, provider)
        self.vms = list(vms)


def _single_circuit(run_input: QuantumCircuit | list[QuantumCircuit]) -> QuantumCircuit:
    if isinstance(run_input, QuantumCircuit):
        return run_input
    circuits = list(run_input)
    if len(circuits) != 1 or not isinstance(circuits[0], QuantumCircuit):
        raise ValueError(f"run() takes one QuantumCircuit (max_circuits = 1), got {len(circuits)}")
    return circuits[0]
