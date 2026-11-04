from collections.abc import Generator, Iterable
import itertools
from pathlib import Path
import random

from benchmark.preparation import Batch


def _initialize_benchmark_path() -> Path:
    """Preprocess the path at which to retrieve the QASMBench cases.

    Returns:
        Path: a path
    """
    relative_path = Path(__file__) / "../../../../misc/QASMBench"
    return relative_path.resolve()


BENCHMARK_PATH = _initialize_benchmark_path()

# Cases identified as invalid by either direct experimentation or by HyperQ
# benchmark
# See-also: https://github.com/1640675651/HyperQ/blob/main/benchmark.py#L42
INVALID_CASES = {
    "ipea_n2",
    "inverseqft_n4",
    "vqe_uccsd_n4",
    "pea_n5",
    "qec_sm_n5",
    "shor_n5",
    "vqe_uccsd_n6",
    "hhl_n7",
    "sat_n7",
    "vqe_uccsd_n8",
    "qpe_n9",
    "adder_n10",
    "hhl_n10",
    "cc_n12",
    "hhl_n14",
    "factor247_n15",
    "bwt_n21",
    "vqe_n24",
    "gcm_n13",
}


def _preprocess(cases: Iterable[Path]) -> Generator[Batch, None, None]:
    """Preprocess an iterable of paths to OpenQASM files and yield them back.

    Args:
        cases (Iterable[Path]): an iterable of paths to OpenQASM files

    Returns:
        Generator[Batch, None, None]: An iterable of Batch instances
    """
    iterator = iter(cases)

    while slice := itertools.islice(iterator, random.randint(2, 7)):
        names = (case.stem for case in slice)
        circuits = (Path.read_text(case / f"{case.stem}.qasm") for case in slice)

        batch = Batch(names, circuits)

        if len(batch) < 1:
            break

        yield batch


def _iterate_over(category: str) -> Generator[Batch, None, None]:
    """Iterate over a category of QASMBench and return batches of cases.

    Args:
        category (str): a QASMBench category

    Returns:
        Generator[Batch, None, None]: an iterable of batches of cases

    Raises:
        AssertionError: if the category doesn't exist
    """
    root_path = BENCHMARK_PATH / category

    assert root_path.is_dir(), f"There is no such category as {category}"

    cases = (
        case
        for case in root_path.iterdir()
        if case.is_dir() and case.stem not in INVALID_CASES
    )

    yield from _preprocess(cases)


def qasmbench_small() -> Generator[Batch, None, None]:
    """Iterate over the small category of the QASMBench project.

    Returns:
        Generator[Batch, None, None]: an iterable of batches of cases

    See-Also:
        https://github.com/pnnl/QASMBench/tree/master/small
    """
    yield from _iterate_over("small")


def qasmbench_medium() -> Generator[Batch, None, None]:
    """Iterate over the small category of the QASMBench project.

    Returns:
        Generator[Batch, None, None]: an iterable of batches of cases

    See-Also:
        https://github.com/pnnl/QASMBench/tree/master/medium
    """
    yield from _iterate_over("medium")


__all__ = [
    "qasmbench_small",
    "qasmbench_medium",
]
