from collections.abc import Generator

from benchmark.preparation import Batch
from benchmark.preparation.cases.qasmbench import (
    qasmbench_small,
    qasmbench_medium,
)


def get_cases() -> Generator[Batch, None, None]:
    """Return the benchmark cases.

    Returns:
        list[list[str]]: A list of batchs containing circuits in OpenQASM
                         format.
    """
    yield from qasmbench_small()
    yield from qasmbench_medium()


__all__ = ["get_cases"]
