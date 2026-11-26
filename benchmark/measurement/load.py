import warnings
from qiskit.providers.exceptions import JobError
from benchmark.experiment import Experiment
from benchmark.measurement.globals import (
    Record,
    circuits_results,
    counts_per_circuits,
    runtime_results,
)


def _load_record(target: str, record: Record) -> None:
    """Load the experiment results record into its right database.

    Meant to be used a temporary method while I figure out what's the best way
    to store all this huge chunk of data.

    Args:
        target (str): a database name
        record (dict): a record
    """
    if target == "runtime":
        runtime_results.append(record)
    elif target == "circuits":
        circuits_results.append(record)
    elif target == "counts":
        key = record.pop("circuit")
        value = record.pop("counts")
        counts_per_circuits[key] = value
    else:
        raise KeyError(target)


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
    job_id = experiment.job.id
    n_qubits = experiment.n_qubits
    total_qubits = experiment.backend.num_qubits

    try:
        results = experiment.job.result()
    except JobError:
        warnings.warn(
            f"Execution failed for job {job_id} containing the followings "
            f"circuits: {experiment.job.circuits}. Its results will not be "
            "added to the benchmark records."
        )
        return False

    duration = experiment.job.duration()

    for name, counts in results.items():
        # NOTE: almost every metric can be computed from the experiment alone.
        #       this is not the case for fidelity: it can be only computed
        #       using a reference, which is a run of the circuit in a noiseless
        #       environment
        circuit_record = {
            "name": name,
            "duration": duration,
            "job_id": job_id,
        }
        _load_record("circuits", circuit_record)

        counts_record = {
            "circuit": name,
            "counts": counts,
        }
        _load_record("counts", counts_record)

    runtime_record = {
        "job_id": job_id,
        "n_qubits": n_qubits,
        "n_circuits": experiment.n_circuits,
        "duration": duration,
        "throughput": round(n_qubits / total_qubits, 6),
    }
    _load_record("runtime", runtime_record)

    return True


__all__ = ["load_record"]
