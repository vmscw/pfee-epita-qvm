import json
from pathlib import Path
from typing import Any

import polars as pl

from benchmark.config import invoke_config
from benchmark.measurement.globals import (
    BenchmarkDatabase,
    circuits_results,
    counts_per_circuits,
    runtime_results,
)

CIRCUITS_SCHEMA = pl.Schema(
    {
        "name": pl.String,
        "duration": pl.Float32,
        "job_id": pl.String,
    }
)
RUNTIME_SCHEMA = pl.Schema(
    {
        "job_id": pl.String,
        "n_qubits": pl.Int16,
        "n_circuits": pl.Int8,
        "duration": pl.Float32,
        "throughput": pl.Float16,
    }
)


def _save_value(value: Any, at: Path) -> Path:
    """Save a plain Python value at the specified path.

    Args:
        value (Any): a value
        at (Path): a folder path

    Returns:
        Path: at
    """
    at.parent.mkdir(parents=True, exist_ok=True)
    at.write_text(str(value))
    return at


def _save_structured_database(
    database: BenchmarkDatabase, at: Path, schema: pl.Schema
) -> Path:
    """Save the benchmark results database at the specified path.

    This stores the database in CSV format, so it is only fit for tabular data.

    Args:
        database (BenchmarkDatabase): a database
        at (Path): a folder path

    Returns:
        Path: The path at which the database is stored
    """
    dataframe = pl.DataFrame(database, schema=schema)
    actual_at = at.with_suffix(".csv")
    dataframe.write_csv(actual_at)
    return actual_at


def _save_unstructured_database(database: BenchmarkDatabase, at: Path) -> Path:
    """Save the benchmark results database at the specified path.

    This stores the database in JSON format, so it is only fit for non-tabular
    data.

    Args:
        database (BenchmarkDatabase): a database
        at (Path): a folder path

    Returns:
        Path: The path at which the database is stored
    """
    formatted_database = json.dumps(database)
    actual_at = at.with_suffix(".jsonl")
    return _save_value(formatted_database, at=actual_at)


def save_metadata(name: str, scheduler: Scheduler, backend: Backend) -> Path:
    config = invoke_config()

    metadata_output_path = config.artefacts_dir / name / "metadata.json"

    metadata = {
        "benchmark_name": name,
        "backend": backend.name,
        "num_qubits": backend.num_qubits,
        "num_shots": config.num_shots,
        "scheduler": scheduler.name,
        "seed": config.seed,
    }
    metadata_formatted = json.dumps(metadata)

    return _save_value(metadata_formatted, at=metadata_output_path)


def save_measurements(name: str) -> tuple[Path, Path, Path]:
    config = invoke_config()

    circuits_output_path = config.artefacts_dir / name / "circuits"
    runtime_output_path = config.artefacts_dir / name / "runtime"
    counts_output_path = config.artefacts_dir / name / "counts"

    assert circuits_output_path is not None
    assert runtime_output_path is not None

    return (
        _save_structured_database(
            circuits_results,
            at=circuits_output_path,
            schema=CIRCUITS_SCHEMA,
        ),
        _save_structured_database(
            runtime_results,
            at=runtime_output_path,
            schema=RUNTIME_SCHEMA,
        ),
        _save_unstructured_database(counts_per_circuits, at=counts_output_path),
    )
