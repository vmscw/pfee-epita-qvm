from collections import Counter

from ultraq_backend import ChipLayout, Hypervisor

from benchmark.preparation.backend import Backend
from benchmark.preparation.batch import Batch


class UltraQJob:
    """Implementation of a job generated from a UltraQ scheduler."""


class UltraQ:
    """QVM allocator as originally conceived by Tao and al, with a twist.

    Adapted to fit on more backends, like a IQM chip.

    See-Also:
        https://dl.acm.org/doi/10.5555/3767901.3767924

    Args:
        backend (Backend): a quantum backend to use to process the circuits
    """

    def __init__(self, backend: Backend):
        self.backend: Backend = backend
        self.layout: ChipLayout

    def run(self, batch: Batch) -> list[UltraQJob]:
        jobs = []

        with Hypervisor()

        return jobs



__all__ = ["HyperQ", "HyperQJob"]
