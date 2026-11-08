"""The hypervisor: job queue, request checks and run loop, in the user's process.

`submit` takes a Qiskit circuit already compiled for its request (a category,
or a group of VMs to fuse), checks it once and queues it. A background thread,
started with the hypervisor, runs the queue every `interval` seconds: it turns
the queue into batches, scheduler (decisions `(Job, vms)`) -> mapper
(physical qubits) -> executor (composite circuit + run). Jobs submitted in the
same window can share a batch; `result()` only waits; `stop()` (or leaving a
`with Hypervisor(...) as hv:` block) ends the thread and runs what is left.

This module must not know any vendor (the `ChipLayout` carries the chip); running a
batch is delegated to the `Executor`.
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Self

from qiskit import QuantumCircuit

from ultraq_backend.model.chip_layout import ChipLayout
from ultraq_backend.model.chips import PhysicalChip
from ultraq_backend.model.jobs import Job, JobState
from ultraq_backend.model.virtual_topology import VirtualTopology
from ultraq_backend.steps.executor import Executor
from ultraq_backend.steps.mapping import Mapper
from ultraq_backend.steps.scheduler import Scheduler
from ultraq_backend.steps.validation import check_circuit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
"""Root of the project (parent of the `ultraq_backend` package)."""

_POLL = 0.2  # seconds: how often a waiting `result()` checks that the background thread is alive


class Hypervisor:
    """Single-process qVM hypervisor.

    chip_layout: a `PhysicalChip` (default layout: the whole chip as one VM,
                 see `ChipLayout.whole_chip`), a `ChipLayout`, or the path of a
                 layout JSON file cutting the chip into several VMs (relative
                 paths are resolved against `PROJECT_ROOT`).
    executor:    the `Executor` running the batches; default `Executor()` (Aer).
                 Any object with the same `execute(batch, shots)` works (e.g.
                 a fake one).
    interval:    seconds between two runs of the queue by the background
                 thread (started here, a daemon thread); must be > 0.

    Use it as a context manager (`with Hypervisor(...) as hv:`) or call
    `stop()` when done.

    Attributes: `chip_layout`, `virtual_topology` (categories and VMs), `jobs`
    ({job_id: Job}, every submitted job with its status, counts or error),
    `queue` (the jobs still waiting, in arrival order), `history` (per
    executed batch, the list of (job_id, VM names used)).
    """

    def __init__(
        self,
        chip_layout: PhysicalChip | ChipLayout | str | Path,
        executor: Executor | None = None,
        interval: float = 0.5,
    ) -> None:
        if not interval > 0:
            raise ValueError(f"interval must be > 0, got {interval!r}")
        if isinstance(chip_layout, PhysicalChip):
            chip_layout = ChipLayout.whole_chip(chip_layout)
        elif not isinstance(chip_layout, ChipLayout):
            path = Path(chip_layout)
            chip_layout = ChipLayout.from_file(path if path.is_absolute() else PROJECT_ROOT / path)
        self.chip_layout = chip_layout
        self.executor = executor if executor is not None else Executor()
        self.scheduler = Scheduler(self.virtual_topology)
        self.mapper = Mapper(self.chip_layout)
        self.jobs: dict[str, Job] = {}
        self.queue: list[Job] = []
        self.history: list[list[tuple[str, list[str]]]] = []
        # One lock for all the state above; `_changed` wakes `result()` up.
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._running = threading.Lock()  # one batch at a time: all VMs are free at each round
        self._stop = threading.Event()
        self._thread: threading.Thread | None = threading.Thread(
            target=self._loop, args=(interval,), name="ultraq-hypervisor", daemon=True
        )
        self._thread.start()

    @property
    def virtual_topology(self) -> VirtualTopology:
        """Categories, VMs and basis gates (Qiskit names) of the layout."""
        return self.chip_layout.virtual_topology

    # ------------------------------------------------------------ jobs

    def submit(
        self,
        circuit: QuantumCircuit,
        *,
        category: str | None = None,
        vms: list[str] | None = None,
        shots: int = 1024,
    ) -> str:
        """Check and queue a circuit; return its job id.

        The circuit must run as-is on `virtual_topology.graph(category=...,
        vms=...)` (see `ultraq_backend.steps.validation.check_circuit`): transpile it
        on `virtual_topology.target(...)` first; otherwise the ValueError says so.
        Category job: the scheduler picks a free VM. Fused job: it waits until
        all its VMs are free; the order of `vms` does not matter (the request
        keeps them in declaration order, see `fuse`). Raises ValueError if
        anything is invalid, RuntimeError after `stop()`.
        """
        graph = self.virtual_topology.graph(category=category, vms=vms)
        if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots!r}")
        try:
            check_circuit(circuit, graph, self.virtual_topology.basis_gates)
        except ValueError as exc:
            where = f"category {category!r}" if category is not None else f"VMs {list(vms)}"
            raise ValueError(
                f"circuit {circuit.name!r} cannot run as-is on {where}: {exc}. "
                "Transpile it first on that target (e.g. `transpile(qc, backend)`)."
            ) from exc
        if category is not None:
            request = {"category": category}
        else:  # canonical order: the same fused graph whatever the order given
            request = {"vms": self.virtual_topology.canonical_vms(vms)}
        job = Job(uuid.uuid4().hex, request, shots, circuit)
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("hypervisor stopped: create a new one to submit jobs")
            self.jobs[job.job_id] = job
            self.queue.append(job)
        return job.job_id

    def job(self, job_id: str) -> Job:
        """The `Job` of `job_id` (with its status, counts or error); KeyError if unknown."""
        if job_id not in self.jobs:
            raise KeyError(f"unknown job_id {job_id!r}")
        return self.jobs[job_id]

    def status(self, job_id: str) -> JobState:
        """Status of a job (QUEUED, RUNNING, DONE or ERROR); KeyError for an unknown id."""
        return self.job(job_id).status

    def result(self, job_id: str, timeout: float | None = None) -> dict[str, int]:
        """Counts of a job ({bitstring: int}, bit 0 rightmost); waits until it is done.

        Waits at most `timeout` seconds if given (then TimeoutError). Raises
        KeyError for an unknown id, RuntimeError if the job failed (its cause
        is chained and kept in `job.error`) and RuntimeError if the job can no
        longer finish (background thread dead, or hypervisor stopped).
        """
        job = self.job(job_id)
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._changed:
            while not _finished(job):
                thread = self._thread
                if thread is None:
                    raise RuntimeError(f"job {job_id} is {job.status} but the hypervisor is stopped")
                if not thread.is_alive() and not self._stop.is_set():  # (set: `stop()` is draining)
                    raise RuntimeError(
                        f"job {job_id} is {job.status} but the hypervisor thread died (see its traceback)"
                    )
                wait = _POLL if deadline is None else min(_POLL, deadline - time.monotonic())
                if wait <= 0:
                    raise TimeoutError(f"job {job_id} still {job.status} after {timeout} s")
                self._changed.wait(wait)
        if job.status == JobState.ERROR:
            raise RuntimeError(f"job {job_id} failed: {job.error}") from job.error
        return job.counts

    # ------------------------------------------------------------ background thread

    def stop(self) -> None:
        """Stop the background thread (after its current batch) and run what is
        left in the queue, so that no job stays QUEUED. Idempotent."""
        thread = self._thread
        if thread is None:
            return
        with self._lock:
            self._stop.set()  # from now on `submit` refuses jobs
        thread.join()
        self._run_queue()
        with self._changed:
            self._thread = None
            self._changed.notify_all()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _loop(self, interval: float) -> None:
        while not self._stop.wait(interval):
            self._run_queue()

    def _run_queue(self) -> None:
        """Schedule, map and execute batches until the queue is empty.

        Each round: scheduler (decisions) -> mapper (physical qubits) ->
        executor (composite circuit + run). The state is updated under the
        lock; the execution itself runs outside it, so `submit` is never
        blocked by a running batch. Never raises because of a job: jobs that
        can never be placed, and the jobs of a round whose scheduling,
        mapping or execution fails, are marked ERROR with their cause in
        `job.error` (a failed scheduling fails every job it was given; a
        failed mapping or execution fails the jobs of that batch only).
        """
        with self._running:
            self._run_batches()

    def _run_batches(self) -> None:
        while True:
            with self._lock:
                if not self.queue:
                    return
                taken = self.queue
                try:
                    decisions, self.queue = self.scheduler.schedule(taken)
                except Exception as exc:  # a scheduler bug must not leave jobs hanging
                    self.queue = []
                    for job in taken:
                        self._finish(job, error=exc)
                    return
                if not decisions:
                    for job in self.queue:
                        self._finish(job, error=RuntimeError(f"job {job.job_id} can never be placed"))
                    self.queue = []
                    return
                jobs = [job for job, _ in decisions]
                try:
                    batch = self.mapper.map(decisions)
                except Exception as exc:  # e.g. an inconsistent layout: fail this batch only
                    for job in jobs:
                        self._finish(job, error=exc)
                    continue
                for job in jobs:
                    job.status = JobState.RUNNING
            try:
                counts = self.executor.execute(batch.jobs, batch.shots)
                if len(counts) != len(batch.jobs):
                    raise RuntimeError(
                        f"executor returned {len(counts)} results for {len(batch.jobs)} jobs"
                    )
            except Exception as exc:  # the target may raise anything
                with self._lock:
                    for job in jobs:
                        self._finish(job, error=exc)
                continue
            with self._lock:
                self.history.append([(job.job_id, list(vms)) for job, vms in decisions])
                for job, job_counts in zip(jobs, counts, strict=True):
                    self._finish(job, counts=dict(job_counts))

    def _finish(self, job: Job, counts: dict[str, int] | None = None, error: Exception | None = None) -> None:
        """Mark `job` DONE with its counts, or ERROR with its cause (lock held), and wake `result()` up."""
        job.counts, job.error = counts, error
        job.status = JobState.ERROR if error is not None else JobState.DONE
        self._changed.notify_all()

    def __repr__(self) -> str:
        return (
            f"Hypervisor({len(self.virtual_topology.categories)} categories, "
            f"{len(self.virtual_topology.vms)} VMs, executor={type(self.executor).__name__})"
        )


def _finished(job: Job) -> bool:
    return job.status in (JobState.DONE, JobState.ERROR)
