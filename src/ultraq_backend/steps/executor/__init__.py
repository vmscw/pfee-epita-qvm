"""Executor step: the composite circuit of a batch and its run on a target.

- `executor.py`: `Executor` (abstract: the composite circuit, the run on a
  Qiskit backend, the counts per job; subclasses create the backend in
  `make_backend`) and `split_counts`;
- `aer.py`: `AerExecutor`, local Aer simulator (the default);
- `iqm.py`: `IQMExecutor(chip)`, a real IQM chip through iqm-client.

The executor must not know the VMs, the queue nor the scheduling policy.
"""

from ultraq_backend.steps.executor.aer import AerExecutor
from ultraq_backend.steps.executor.executor import Executor, split_counts
from ultraq_backend.steps.executor.iqm import IQMExecutor, check_qubit_order

__all__ = ["AerExecutor", "Executor", "IQMExecutor", "check_qubit_order", "split_counts"]
