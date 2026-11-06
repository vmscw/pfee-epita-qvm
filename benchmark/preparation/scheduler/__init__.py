from collections import Counter
from typing import Protocol, Type

from benchmark.preparation import Backend, Batch
from benchmark.preparation.scheduler.hyperq import HyperQ
from benchmark.preparation.scheduler.sequential import Sequential


class Scheduler(Protocol):
    """Interface of a arbitrary quantum virtual machines scheduler.

    To ensure processing linearity, all scheduling engines to be benchmarked
    are queried through the mean of a wrapper which provide a common interface
    for all.

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend): ...

    def run(self, batch: Batch) -> dict[str, Counter]:
        """Run the circuits from the batch.

        Args:
            batch (Batch): a batch of circuits to run

        Returns:
            dict[str, Counter]: the bitstring distribution received for each
                                circuit
        """


SCHEDULER_NAMES: dict[str, Type[Scheduler]] = {
    "HyperQ": HyperQ,
    "Sequential": Sequential,
    "hyperq": HyperQ,
    "hyper_q": HyperQ,
    "sequential": Sequential,
}


def get_scheduler(name: str, *, backend: Backend) -> Scheduler:
    """Return a scheduler to benchmark based on its name.

    Args:
        name (str): a name
        backend (Backend): a backend to provide to the scheduler

    Returns:
        Scheduler: The corresponding scheduler.

    Raises:
        ValueError: if the specified name doesn't correspond to any actual
                    scheduler
    """
    scheduler_type: Type[Scheduler] | None = SCHEDULER_NAMES.get(name, None)

    if scheduler_type is None:
        raise ValueError(f"{name} doesn't refer to any scheduler type")

    return scheduler_type(backend)


__all__ = [
    "HyperQ",
    "Scheduler",
    "Sequential",
    "get_scheduler",
]
