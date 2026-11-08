from typing import TypedDict

from benchmark.experiment import Experiment


class BenchmarkResults(TypedDict):
    """The results of the benchmark."""


def measure(results: Experiment) -> bool:
    """Add the run results to the benchmark results.

    Args:
        results (RunResults): The result of a experiment

    Returns:
        bool: True if all metrics could have been extracted from results.
              False otherwise.
    """
    # we need
    #   - the fidelity
    #   - the throughput

    raise NotImplementedError


def get_measurements() -> BenchmarkResults:
    """Get the formatted dictionnary of the benchmark results.

    Returns:
        BenchmarkResults: The benchmark results, formatted as a regular
                          dictionnary.
    """
    raise NotImplementedError


__all__ = [
    "BenchmarkResults",
    "get_measurements",
    "measure",
]
