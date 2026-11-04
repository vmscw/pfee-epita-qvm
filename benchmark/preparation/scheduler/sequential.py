from collections import Counter

from benchmark.preparation.backend import Backend
from benchmark.preparation.batch import Batch


class Sequential:
    """Fake scheduler. Runs all circuits separately.

    Typically used to retrieve the performance of each benchmark case when run
    alone on the QPU.

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        self.backend: Backend = backend

    def run(self, batch: Batch) -> dict[str, Counter]:
        return {name: self.backend.run(circuit) for name, circuit in batch}


__all__ = ["Sequential"]
