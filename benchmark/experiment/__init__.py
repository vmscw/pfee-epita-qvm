from collections.abc import Sequence

from benchmark.preparation import Batch, Job, Scheduler


class Experiment:
    """High-level representation of an experiment."""
    def __init__(self, job: Job):
        self.job = job
        self.n_circuits = len(job.circuits)
        self.n_qubits = sum(len(qvm) for qvm in job.qvms)


def run(scheduler: Scheduler, batch: Batch) -> Sequence[Experiment]:
    """Run an experiment based on the given scheduler and a batch of cases.

    Many experiments for a same batch may be returned if the scheduler cannot
    run all the circuits in the batch in one job. The circuits will then be
    divided in many jobs.

    Args:
        scheduler (Scheduler): a scheduler
        batch (Batch): a batch of cases

    Returns:
        ExperimentResults: A list of experiment.
    """
    jobs = scheduler.run(batch)
    return [Experiment(job) for job in jobs]


__all__ = ["Experiment", "run"]
