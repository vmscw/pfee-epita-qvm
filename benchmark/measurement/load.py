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
        counts_per_circuits.append(record)
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
