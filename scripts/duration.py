from argparse import ArgumentParser
from pathlib import Path

import polars as pl


def define_parser() -> ArgumentParser:
    """Define an argument parser.

    There is only one required argument: valid paths, which refer to a
    benchmark output folder.

    Returns:
        ArgumentParser: an argument parser
    """
    parser = ArgumentParser()

    parser.add_argument("benchmark", type=Path)

    return parser


def parse(parser: ArgumentParser) -> Path:
    """Parse the program arguments using the parser.

    Returns a valid path as explained in the documentation of `define_parser()`.

    Returns:
        Path: a path refering to a benchmark

    See-Also:
        `define_parser`
    """
    args = parser.parse_args()
    return args.benchmark


def main():
    """Main callback."""
    parser = define_parser()
    benchmark_folder = parse(parser)

    if not benchmark_folder.is_dir():
        raise ValueError(f"{benchmark_folder} is not a directory")

    runtime_file = benchmark_folder / "runtime.csv"

    if not runtime_file.is_file():
        raise ValueError(f"{runtime_file} is not a file")

    runtime = pl.read_csv(runtime_file)
    total_circuits = runtime["n_circuits"].sum()
    total_duration_ms = runtime["duration"].sum()

    print(f"{total_circuits} circuits handled in {total_duration_ms}ms")


if __name__ == "__main__":
    main()


__all__ = ["main"]
