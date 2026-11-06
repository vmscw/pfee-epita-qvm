from collections import Counter
from collections.abc import Sequence

from benchmark.preparation import Batch, Scheduler


class ExperimentResults:
    def __init__(self, counts: dict[str, Counter]):
        self.names = list(counts.keys())
        self.counts = counts


def run(scheduler: Scheduler, batch: Batch) -> ExperimentResults:
    """Run an experiment based on the given scheduler and a batch of cases.

    Args:
        scheduler (Scheduler): a scheduler
        batch (Batch): a batch of cases

    Returns:
        ExperimentResults: The results of the experiment.
    """
    counts = scheduler.run(batch)
    return ExperimentResults(counts)


__all__ = ["ExperimentResults", "run"]
