from datetime import datetime
from os import PathLike
import random
import warnings

from benchmark.config import invoke_config
from benchmark.experiment import run
from benchmark.measurement import measure, save_measurements
from benchmark.preparation import get_cases, get_backend, get_scheduler


def setup_benchmark() -> None:
    """Run all the processes to run before starting the benchmark.

    Such things include, for example, setting up randomization seeds.
    """
    CONFIG = invoke_config()

    random.seed(CONFIG.seed)


def run_benchmark() -> tuple[PathLike, PathLike]:
    """Run a benchmark and return its results.

    Returns:
        BenchmarkResults: The benchmark results
    """
    CONFIG = invoke_config()

    name = CONFIG.benchmark_name

    if name is None:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        name = "{}-{}-{}".format(CONFIG.scheduler, CONFIG.backend, timestamp)

    batches = get_cases()
    backend = get_backend(CONFIG.backend)
    scheduler = get_scheduler(CONFIG.scheduler, backend=backend)

    for batch in batches:
        for experiment in run(scheduler, batch):
            measure(experiment)

    return save_measurements(name)


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
