from datetime import datetime
import logging
from os import PathLike
from pathlib import Path
import random
import warnings

from benchmark.config import invoke_config
from benchmark.experiment import run
from benchmark.measurement import measure, save_measurements, save_metadata
from benchmark.preparation import get_cases, get_backend, get_scheduler


LOADING_BENCHMARK = "Loadng benchmark {} with args: scheduler: {}, backend: {}"
STARTING_BENCHMARK = "Starting benchmark {}"
GENERATING_EXPERIMENT = "Generating experiments for batch containing {} circuits: {}"
WAITING_FOR_EXPERIMENT = "Started experiment with job id {} containing {} circuits: {}"


logging.basicConfig(
    format="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S",
)
logger = logging.getLogger("benchmark")


def setup_benchmark() -> None:
    """Run all the processes to run before starting the benchmark.

    Such things include, for example, setting up randomization seeds.
    """
    CONFIG = invoke_config()

    logger.setLevel(logging.DEBUG)
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

    logger.debug(LOADING_BENCHMARK.format(name, CONFIG.scheduler, CONFIG.backend))

    batches = get_cases()
    backend = get_backend(CONFIG.backend)
    scheduler = get_scheduler(CONFIG.scheduler, backend=backend)

    logger.debug(STARTING_BENCHMARK.format(name))

    for batch in batches:
        logger.info(GENERATING_EXPERIMENT.format(len(batch), batch.names))

        for experiment in run(scheduler, backend, batch):
            logger.info(
                WAITING_FOR_EXPERIMENT.format(
                    experiment.job.id, experiment.n_circuits, experiment.job.circuits
                ),
            )
            measure(experiment)

    output = save_metadata(name, scheduler, backend)
    save_measurements(name)

    return output.parent


def main() -> None:
    setup_benchmark()

    output_folder = run_benchmark()

    print("Artefacts have been stored at:", output_folder.absolute())


if __name__ == "__main__":
    main()


__all__ = [
    "define_parser",
    "load_config",
    "main",
    "run_benchmark",
]
