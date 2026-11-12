from pathlib import Path
import json
from typing import Any

from benchmark.config import invoke_config
from benchmark.preparation import Backend, Scheduler
from benchmark.experiment import Experiment


type BenchmarkDatabase = list[dict[str, Any]]

runtime_results: BenchmarkDatabase = []
circuits_results: BenchmarkDatabase = []


def _load_record(target: str, record: dict[str, Any]) -> None:
    """Load the experiment results record into its right database.

    Meant to be used a temporary method while I figure out what's the best way
    to store all this huge chunk of data.

    Params:
        target (str): a database name
        record (dict): a record
    """
    if target == "runtime":
        runtime_results.append(record)
    elif target == "circuits":
        circuits_results.append(record)
    else:
        raise KeyError(target)


def _save_value(value: Any, at: Path) -> Path:
    """Save a plain Python value at the specified path.

    Params:
        value (Any): a value
        at (Path): a folder path

    Returns:
        Path: at
    """
    at.parent.mkdir(parents=True, exist_ok=True)
    at.write_text(str(value))
    return at


def _save_database(database: BenchmarkDatabase, at: Path) -> Path:
    """Save the benchmark results database at the specified path.

    Params:
        database (BenchmarkDatabase): a database
        at (Path): a folder path

    Returns:
        Path: The path at which the database is stored
    """
    formatted_database = json.dumps(database)
    actual_at = at.with_suffix(".jsonl")
    return _save_value(formatted_database, at=actual_at)


def measure(experiment: Experiment) -> bool:
    """Add the results of an experiment to the benchmark results.

    During measurements, the following metrics are computed.

    For each job:
        duration (float): the total processing time of the job in the backend
        throughput (float): the utilization rate of the backend qubits by the
                            job

    For each circuit:
        counts (Counter): the total occurences of each state measured at the
                          end of the circuit. this is necessary to compute the
                          fidelity using a reference run (from a noiseless
                          simulation) afterwards

    Args:
        experiment (Experiment): an experiment

    Returns:
        bool: True if all metrics could have been extracted from results.
              False otherwise.
    """
    # NOTE: in IBM Quantum Runtime, one may retrieve the total runtime
    #       duration of a job directly using job.usage(). this is thanks
    #       to a special method usage() that belongs specifically to the
    #       RuntimeJobV2 only available with the IBM runtime
    #       the Scaleway runtime and Qiskit AER jobs return instances of JobV1,
    #       which doesn't have this method. thus, there might be no way to know
    #       the total duration of a job yet

    # FIXME: find a way to retrieve the total runtime duration of a job

    # See-Also:
    #   https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/runtime-job-v2#usage
    duration = 0.0

    job_id = experiment.job.id
    n_qubits = experiment.n_qubits
    total_qubits = experiment.backend.num_qubits
    results = experiment.job.result()

    for name, counts in results.items():
        # NOTE: almost every metric can be computed from the experiment alone.
        #       this is not the case for fidelity: it can be only computed
        #       using a reference, which a run of the circuit in a noiseless
        #       environment
        circuit_record = {
            "name": name,
            "counts": counts,
            "duration": duration,
            "job_id": job_id,
        }
        _load_record("circuits", circuit_record)

    runtime_record = {
        "job_id": job_id,
        "n_qubits": n_qubits,
        "n_circuits": experiment.n_circuits,
        "duration": duration,
        "throughput": round(n_qubits / total_qubits, 6),
    }
    _load_record("runtime", runtime_record)

    return True


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


def save_measurements(name: str) -> tuple[Path, Path]:
    config = invoke_config()

    circuits_output_path = config.artefacts_dir / name / "circuits"
    runtime_output_path = config.artefacts_dir / name / "runtime"

    assert circuits_output_path is not None
    assert runtime_output_path is not None

    _save_database(circuits_results, at=circuits_output_path)
    _save_database(runtime_results, at=runtime_output_path)

    return circuits_output_path, runtime_output_path


__all__ = [
    "BenchmarkDatabase",
    "measure",
    "save_measurements",
    "save_metadata",
]
