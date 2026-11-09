import json
import sys
from argparse import ArgumentParser
from pathlib import Path

import shtab


def define_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="metrics")
    shtab.add_argument_to(parser, ["-s", "--print-completion"])

    parser.add_argument("--benchmark", type=Path).complete = shtab.FILE
    parser.add_argument("--baseline", type=Path).complete = shtab.FILE

    return parser


def parse(parser: ArgumentParser) -> tuple[Path | None, Path | None]:
    args = parser.parse_args()
    return args.benchmark, args.baseline


def get_metrics(
    benchmark_file: Path, baseline_file: Path
) -> tuple[float, float, float]:
    benchmark = json.loads(benchmark_file.read_text())
    baseline = json.loads(baseline_file.read_text())

    fidelity = ...
    throughput = ...
    speedup = ...

    return -1, -1, -1


def main():
    parser = define_parser()
    benchmark, baseline = parse(parser)

    if benchmark is None or baseline is None:
        print(parser.format_usage(), end="")
        sys.exit(1)

    if not benchmark.is_dir():
        print(f"error: {benchmark} is not a directory")
        sys.exit(2)

    if not baseline.is_dir():
        print(f"error: {baseline} is not a directory")
        sys.exit(2)

    metrics = get_metrics(benchmark.resolve(), baseline.resolve())
    print(metrics)


__init__ = ["main"]
