"""IQMExecutor: the batches on a real IQM chip, through an iqm-client Qiskit backend.

`IQMBackend.run` does not transpile: the composite circuit runs as-is on the
physical qubits chosen by ultraq (the IQM server only checks it against the
chip's DQA). The chip (`ultraq_backend.model.chips.iqm`) describes the
hardware; this module only connects to it to run circuits.

iqm-client is imported only inside `IQMExecutor.make_backend`, so importing
ultraq (e.g. for an Aer run) does not pay for loading it.
"""

from __future__ import annotations

import logging
from typing import Any

from ultraq_backend.env import from_env
from ultraq_backend.model.chips import IQMEmerald, IQMGarnet, PhysicalChip
from ultraq_backend.steps.executor.executor import Executor

log = logging.getLogger(__name__)


class IQMExecutor(Executor):
    """`Executor` on the iqm-client backend of `chip`.

    Pins the calibration set of the chip's snapshot, so the active qubits and
    couplers are those the layout was built on. The server is always
    `IQM_URL` (env or `.env`), never an argument. The run token is always `IQM_TOKEN`: iqm-client
    reads it from the environment itself (it refuses a `token` argument when
    that variable is set), we only load `.env` and check it is there.
    run_options / result_options: see `Executor`.

    `chip`: the chip this executor runs on.
    Raises ValueError if the chip has no calibration set or if backend qubit
    i is not chip qubit i; RuntimeError if IQM_TOKEN is missing.
    """

    def __init__(
        self,
        chip: IQMGarnet | IQMEmerald,
        run_options: dict[str, Any] | None = None,
        result_options: dict[str, Any] | None = None,
    ) -> None:
        self.chip = chip
        super().__init__(run_options, result_options)

    def make_backend(self) -> Any:
        from iqm.qiskit_iqm import IQMProvider

        chip = self.chip
        if chip.calibration_set_id is None:
            raise ValueError(f"chip {chip.id!r} has no calibration_set_id")
        url = from_env("IQM_URL", "IQM server URL")
        from_env("IQM_TOKEN", "IQM run token")  # only checked: iqm-client reads it itself (name imposed)
        provider = IQMProvider(url, quantum_computer=chip.id)
        backend = provider.get_backend(calibration_set_id=chip.calibration_set_id)
        check_qubit_order(backend, chip)
        log.info("IQM backend created: quantum computer %s, calibration set %s, %d qubits",
                 chip.id, chip.calibration_set_id, backend.num_qubits)
        return backend

    def failure_reason(self, job: Any, result: Any) -> str:
        """The IQM server's error message, else the result status."""
        return job.error_message() or super().failure_reason(job, result)


def check_qubit_order(backend: Any, chip: PhysicalChip) -> None:
    """ValueError unless backend qubit i is chip qubit i (same label, e.g. `QB5`) for every i."""
    labels = [chip.graph[i].label for i in chip.graph.node_indices()]
    names = [backend.index_to_qubit_name(i) for i in range(backend.num_qubits)]
    if names != labels:
        raise ValueError(f"qubit order differs: backend {names} vs chip {chip.id!r} {labels}")
    log.debug("qubit order check passed: %d qubits match chip %s", len(names), chip.id)
