from collections import Counter

from benchmark.preparation.backend import Backend
from benchmark.preparation.batch import Batch


class HyperQJob:
    """Implementation of a job generated from a HyperQ scheduler."""


class HyperQ:
    """QVM allocator as originally conceived by Tao and al.

    See-Also:
        https://dl.acm.org/doi/10.5555/3767901.3767924

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        self.backend: Backend = backend

    def run(self, batch: Batch) -> list[HyperQJob]:
        raise NotImplementedError


__all__ = ["HyperQ", "HyperQJob"]
