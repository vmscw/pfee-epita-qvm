"""AerExecutor: the batches on a local, noiseless Aer simulator."""

from __future__ import annotations

from typing import Any

from qiskit_aer import AerSimulator

from ultraq_backend.steps.executor.executor import Executor


class AerExecutor(Executor):
    """`Executor` on `AerSimulator()` (the hypervisor's default executor).

    run_options / result_options: see `Executor` (e.g.
    `run_options={"seed_simulator": 1}` for reproducible counts).
    """

    def make_backend(self) -> Any:
        return AerSimulator()
