from argparse import ArgumentParser
import json
from pathlib import Path
from typing import Any

import polars as pl


FIDELITY_SCHEMA = pl.Schema(
    {
        "circuit": pl.String,
        "l1_score": pl.Float32,
    }
)


def define_parser() -> ArgumentParser:
    """Define an argument parser.

    Required arguments are a couple of two valid paths, which refer to a
    benchmark output folder along with another one to use as reference.

    Typically, the benchmark and its reference will be based on the same
    scheduler, with benchmark being measurements on a noisy/real backend and
    the reference being a view of the circuit outputs on a noiseless engine.

    Returns:
        ArgumentParser: an argument parser
    """
    parser = ArgumentParser()

    parser.add_argument("benchmark", type=Path)
    parser.add_argument("reference", type=Path)

    return parser


def parse(parser: ArgumentParser) -> tuple[Path, Path]:
    """Parse the program arguments using the parser.

    Returns a couple of valid paths as explained in the documentation of
    `define_parser()`.

    Returns:
        tuple[Path, Path]: a couple of paths refering to a benchmark and a
                           reference specified by the user

    See-Also:
        `define_parser`
    """
    args = parser.parse_args()
    return (args.benchmark, args.reference)


def normalize(counts: dict[Any, int]) -> dict[Any, float]:
    """Normalize an event counter to a probability distribution in ]0,1].

    Args:
        counts (dict[Any, int]): an event counter

    Returns:
        dict[Any, int]: the event counter as a probability distribution
    """
    total_counts = sum(counts.values())
    return {event: count / total_counts for event, count in counts.items()}


def l1_score(actual: dict[Any, float], expected: dict[Any, float]) -> float:
    """Returns the L1 score between two probability distributions.

    The L1 score is defined as:
    $ \sum_{event \in EV} {avg(expected_{event} - actual_{event})} $, $ EV $
    representing all output possibilities upon circuit measurement. In other
    words, the closer is the L1 score to 0, the more actual matches expected.

    The L1 score is used by Tao et al to indicate the fidelity of circuits on
    a QVM settings over their expected outputs.

    See-Also:
        https://dl.acm.org/doi/10.5555/3767901.3767924

    Args:
        actual (dict[Any, float]): a probability distribution of actual occurences
        expected (dict[Any, float]): a probability distribution of expected
                                     occurences

    Returns:
        float: a L1 score between `actual` and `expected`
    """
    outcomes = expected.keys() | actual.keys()
    return sum(
        (abs(expected.get(state, 0.0) - actual.get(state, 0.0)) for state in outcomes)
    )


def get_fidelity(benchmark: Path, reference: Path) -> pl.DataFrame:
    """Return the fidelity of a benchmark circuit outputs based on a reference.

    Args:
        benchmark (Path): path to a JSON file of circuit outputs
        reference (Path): path to a JSON file of circuit outputs

    Returns:
        The L1 score of each circuit output probability distribution wrapped in
        a Polars dataframe

    See-Also:
        `define_parser`
    """
    actual = json.loads(benchmark.read_text())
    expected = json.loads(reference.read_text())

    actual = {circuit: normalize(counts) for circuit, counts in actual.items()}
    expected = {circuit: normalize(counts) for circuit, counts in expected.items()}

    circuits = actual.keys() & expected.keys()

    fidelity = [
        {"circuit": circuit, "l1_score": l1_score(actual[circuit], expected[circuit])}
        for circuit in circuits
    ]

    return pl.from_records(fidelity, schema=FIDELITY_SCHEMA)


def save_dataframe(dataframe: pl.DataFrame, at: Path) -> Path:
    """Save the Polars dataframe at the specified path in csv format.

    It is not expected that the specified path contains the csv extension, just
    the filename.

    Args:
        dataframe (pl.DataFrame): a Polars dataframe
        at (Path): a path at which to store a csv output

    Returns:
        at with a .csv suffix
    """
    actual_at = at.with_suffix(".csv")
    dataframe.write_csv(actual_at)
    return actual_at


def main() -> None:
    """Main callback."""
    parser = define_parser()

    benchmark_folder, reference_folder = parse(parser)

    if not benchmark_folder.is_dir():
        raise ValueError(f"{benchmark_folder} is not a directory")

    if not reference_folder.is_dir():
        raise ValueError(f"{reference_folder} is not a directory")

    benchmark = benchmark_folder / "counts.json"
    reference = reference_folder / "counts.json"

    if not benchmark.is_file():
        raise ValueError(f"{benchmark} is not a file")

    if not reference.is_file():
        raise ValueError(f"{reference} is not a file")

    fidelity = get_fidelity(benchmark, reference)

    output_path = save_dataframe(fidelity, at=benchmark_folder / "fidelity")

    print("Result saved at: ", output_path)


if __name__ == "__main__":
    main()


__all__ = ["main"]
