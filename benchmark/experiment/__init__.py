from collections.abc import Sequence

from benchmark.preparation import Batch, Scheduler


class ExperimentResults:
    pass


def run(scheduler: Scheduler, batch: Batch) -> ExperimentResults:
    """Run an experiment based on the given scheduler and a batch of cases.

    Args:
        scheduler (Scheduler): a scheduler
        batch (Batch): a batch of cases

    Returns:
        ExperimentResults: The results of the experiment.
    """
    raise NotImplementedError


__all__ = ["ExperimentResults", "run"]
