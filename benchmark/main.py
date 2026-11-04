from argparse import ArgumentParser
from dataclasses import dataclass
import json
import warnings

from benchmark.preparation import get_backend, get_cases, get_scheduler
from benchmark.experiment import run
from benchmark.measurement import BenchmarkResults, get_measurements, measure


@dataclass
class Config:
    scheduler: str
    backend: str


def define_parser() -> ArgumentParser:
    """Define the CLI arguments parser.

    Returns:
        ArgumentParser: an argument parser
    """
    parser = ArgumentParser(prog="benchmark", usage="%(prog)s [options]")

    parser.add_argument("--scheduler")
    parser.add_argument("--backend")

    return parser


def load_config(parser: ArgumentParser) -> Config:
    """Load the benchmark configuration.

    Args:
        parser (ArgumentParser): an argument parser

    Returns:
        Config: A benchmark configuration
    """
    args = parser.parse_args()

    scheduler = args.scheduler
    backend = args.backend

    return Config(scheduler=scheduler, backend=backend)


def run_benchmark(config: Config) -> BenchmarkResults:
    """Run a benchmark and return its results.

    Args:
        config (Config): a benchmark configuration

    Returns:
        BenchmarkResults: The benchmark results
    """
    batches = get_cases()
    backend = get_backend(config.backend)
    scheduler = get_scheduler(config.scheduler, backend=backend)

    for i, batch in enumerate(batches):
        results = run(scheduler, batch)
        ok = measure(results)

        if not ok:
            message = f"Metrics recording failed on batch {i}"
            warnings.warn(message)

    return get_measurements()


def main() -> None:
    parser = define_parser()
    config = load_config(parser)
    results = run_benchmark(config)

    print(results)


__all__ = [
    "define_parser",
    "load_config",
    "main",
    "run_benchmark",
]
