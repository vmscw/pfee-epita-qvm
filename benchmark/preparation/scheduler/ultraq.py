from collections import Counter
from collections.abc import Sequence, Generator
import json
import time
from typing import Any
import warnings

from iqm.qiskit_iqm import IQMFakeGarnet
from qiskit import transpile
from qiskit.transpiler import Target, TranspilerError

from ultraq_backend import ChipLayout, Hypervisor
from ultraq_backend.model.chips import IQMEmerald, IQMGarnet
from ultraq_backend.model.virtual_topology import VirtualTopology
from ultraq_backend.steps.executor import Executor, IQMExecutor

from benchmark.config import invoke_config
from benchmark.preparation.backend import (
    Backend,
    IQMEmerald54q,
    IQMGarnet20q,
    IQMGarnet20qEmulation,
)
from benchmark.preparation.batch import Batch
from benchmark.utils import qasm2_to_qiskit


def _check_chip(layout: dict, expected: str) -> None:
    """Raise an error is the chip layout does not represent the expected chip.

    Args:
        layout (dict): a layout
        expected (str): a chip name

    Raises:
        ValueError: if the name of the chip represented by layout does not match
                    the expected name
    """
    if layout.get("chip") != expected:
        raise ValueError(
            f"chip layout is for {layout.get('chip')!r} but the backend is {expected!r}"
        )


class CustomExecutor(Executor):
    """A custom executor based on a benchmark backend."""

    def __init__(self, backend: Backend):
        self._backend_factory = backend
        super().__init__()

    def make_backend(self) -> Any:
        return IQMFakeGarnet()


class UltraQJob:
    """One batch executed by UltraQ: the circuits run together in one backend job.

    Args:
        job_id (str): id of the backend job
        circuits (Sequence[str]): benchmark names of the circuits
        qvms (Sequence[Sequence[int]]): physical qubits used by each circuit
        counts (Sequence[dict[str, int]]): counts of each circuit
        duration_s (float): wall time of the batch execution, in seconds
    """

    def __init__(
        self,
        job_id: str,
        circuits: Sequence[str],
        qvms: Sequence[Sequence[int]],
        counts: Sequence[dict[str, int] | None],
    ):
        self.id: str = job_id
        self.circuits: Sequence[str] = list(circuits)
        self.qvms: Sequence[Sequence[int]] = [list(q) for q in qvms]
        self._counts = {name: Counter(c) for name, c in zip(circuits, counts)}
        self._counts = {}

        for name, count in zip(circuits, counts):
            if count is None:
                warnings.warn(f"{name} returned an invalid count, it might have failed")
                count = Counter()

            self._counts[name] = Counter(count)

    def result(self) -> dict[str, Counter]:
        return self._counts

    def duration(self) -> float:
        return 0.0


def _scan_session(
    hypervisor: Hypervisor,
    executor: Executor,
    pretty_names: dict[str, str],
) -> list[UltraQJob]:
    """Retrace back the submission history of a hypervisor to retrieve jobs.

    Args:
        hypervisor (Hypervisor): an hypervisor
        executor (Executor): the executor used by the hypervisor
        pretty_names (dict): a mapping of each hypervisor job to the name of the
                             circuit that was submitted with the job

    Returns:
        list[UltraQJob]: a list of benchmark jobs
    """
    total_jobs = len(hypervisor.history)

    if total_jobs == 0:
        return []

    last_jobs = executor.job_ids[-total_jobs:]

    return [
        UltraQJob(
            backend_job_id,
            circuits=[pretty_names[job_id] for job_id, _ in vms_per_job],
            qvms=[hypervisor.mapper.physical_qubits(vms) for _, vms in vms_per_job],
            counts=[hypervisor.job(job_id).counts for job_id, _ in vms_per_job],
        )
        for vms_per_job, backend_job_id in zip(
            hypervisor.history, last_jobs, strict=True
        )
    ]


class UltraQ:
    """QVM allocator as originally conceived by Tao and al, with a twist.

    Adapted to fit on more backends, like a IQM chip.

    See-Also:
        https://dl.acm.org/doi/10.5555/3767901.3767924

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        config = invoke_config()

        if config.chip_layout_path is None:
            raise ValueError(
                "Attempted to initialize a UltraQ scheduler but no chip layout "
                "file has been specified. Please specify one using the "
                "--chip_layout_path flag."
            )

        self.name = "ultra_q"
        self.backend: Backend = backend
        self._num_shots = config.num_shots
        self._seed = config.seed

        layout = json.loads(config.chip_layout_path.read_text())

        if isinstance(backend, IQMGarnet20qEmulation):
            _check_chip(layout, "garnet")
            warnings.warn(
                f"UltraQ is not compatible with the --debug_circuit_max_size "
                " debug flag. Feel free to add your own fix in the code if you "
                "want to try out the scheduler with a local simulator :)"
            )
            self._layout = ChipLayout.from_dict(layout)
            self._executor: Executor = CustomExecutor(backend)
        elif isinstance(backend, (IQMGarnet20q, IQMEmerald54q)):
            chip_cls = IQMGarnet if isinstance(backend, IQMGarnet20q) else IQMEmerald
            _check_chip(layout, "garnet" if chip_cls is IQMGarnet else "emerald")
            chip = chip_cls.fetch()
            if layout.get("snapshot", "latest") != "latest":
                warnings.warn(
                    f"layout snapshot {layout['snapshot']} ignored: the real chip "
                    f"runs on the fetched snapshot {chip.snapshot}"
                )
            self._layout = ChipLayout.from_dict({**layout, "snapshot": chip.snapshot})
            self._executor = IQMExecutor(self._layout.physical_chip)
        else:
            raise ValueError(
                "Attempted to initialize a UltraQ scheduler but there are no "
                f"chip layout compatible with {backend.name}. Please select "
                "another one (for now: only IQM)."
            )

    def _choose_vm(
        self, topology: VirtualTopology, num_qubits: int
    ) -> tuple[dict | None, Target | None]:
        """Smallest category, else smallest fusion, with >= num_qubits qubits."""
        for category in sorted(topology.categories, key=lambda c: len(c.graph)):
            if len(category.graph) >= num_qubits:
                return (
                    {"category": category.name},
                    topology.target(category=category.name),
                )

        for vms in topology.fusion_candidates(num_qubits):
            return {"vms": vms}, topology.target(vms=vms)

        return None, None

    def run(self, batch: Batch) -> list[UltraQJob]:
        names: dict[str, str] = {}  # UltraQ job id -> benchmark name

        hypervisor = Hypervisor(self._layout, executor=self._executor)
        topology = hypervisor.virtual_topology

        with Hypervisor(self._layout, executor=self._executor) as hypervisor:
            for name, circuit in batch:
                qiskit_circuit = qasm2_to_qiskit(circuit)

                if qiskit_circuit is None or qiskit_circuit.num_qubits > 10:
                    continue

                where, target = self._choose_vm(topology, qiskit_circuit.num_qubits)

                if where is None:
                    warnings.warn(
                        f"circuit {name} ({qiskit_circuit.num_qubits} qubits) fits "
                        "in no VM nor fusion of the layout. Ignoring it."
                    )
                    continue

                try:
                    isa = transpile(
                        qiskit_circuit, target=target, seed_transpiler=self._seed
                    )
                    job_id = hypervisor.submit(isa, shots=self._num_shots, **where)
                except (TranspilerError, ValueError) as e:
                    warnings.warn(f"circuit {name} rejected by UltraQ: {e}")
                    continue

                names[job_id] = name

        for job_id, name in names.items():
            job = hypervisor.job(job_id)
            if job.error is not None:
                warnings.warn(f"circuit {name} failed in UltraQ: {job.error}")

        return _scan_session(hypervisor, self._executor, names)


__all__ = ["UltraQ", "UltraQJob"]
