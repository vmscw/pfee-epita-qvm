import random
import warnings

from benchmark.config import invoke_config
from benchmark.experiment import run
from benchmark.measurement import BenchmarkResults, measure, get_measurements
from benchmark.preparation import get_cases, get_backend, get_scheduler


def setup_benchmark() -> None:
    """Run all the processes to run before starting the benchmark.

    Such things include, for example, setting up randomization seeds.
    """
    CONFIG = invoke_config()

    random.seed(CONFIG.seed)


def run_benchmark() -> BenchmarkResults:
    """Run a benchmark and return its results.

    Returns:
        BenchmarkResults: The benchmark results
    """
    CONFIG = invoke_config()

    batches = get_cases()
    backend = get_backend(CONFIG.backend)
    scheduler = get_scheduler(CONFIG.scheduler, backend=backend)

    for i, batch in enumerate(batches):
        results = run(scheduler, batch)
        ok = measure(results)

        if not ok:
            message = f"Metrics recording failed on batch {i}"
            warnings.warn(message)

    return get_measurements()


def main() -> None:
    setup_benchmark()

    results = run_benchmark()

    print(results)


__all__ = [
    "define_parser",
    "load_config",
    "main",
    "run_benchmark",
]
