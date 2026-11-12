from pathlib import Path
from datetime import datetime
from os import PathLike
import random
import warnings

from benchmark.config import invoke_config
from benchmark.experiment import run
from benchmark.measurement import measure, save_measurements, save_metadata
from benchmark.preparation import get_cases, get_backend, get_scheduler


def setup_benchmark() -> None:
    """Run all the processes to run before starting the benchmark.

    Such things include, for example, setting up randomization seeds.
    """
    CONFIG = invoke_config()

    random.seed(CONFIG.seed)


def run_benchmark() -> Path:
    """Run a benchmark and return its results.

    Returns:
        Path: the root folder of the benchmark artefacts
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
        for experiment in run(scheduler, backend, batch):
            measure(experiment)

    output = save_metadata(name, scheduler, backend)
    save_measurements(name)

    return output.parent


def main() -> None:
    setup_benchmark()

    output_folder = run_benchmark()

    print("Artefacts have been stored at:", output_folder.absolute())


__all__ = [
    "define_parser",
    "load_config",
    "main",
    "run_benchmark",
]
