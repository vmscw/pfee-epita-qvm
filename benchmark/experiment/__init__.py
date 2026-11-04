from collections.abc import Sequence

from benchmark.preparation import Scheduler


class ExperimentResults:
    pass


def run(scheduler: Scheduler, batch: Sequence[str]) -> ExperimentResults:
    """Run an experiment based on the given scheduler and a batch of cases.

    Args:
        scheduler (Scheduler): a scheduler
        batch (Collection[str]): a batch of circuits in OpenQASM format

    Returns:
        ExperimentResults: The results of the experiment.
    """
    raise NotImplementedError


__all__ = ["ExperimentResults", "run"]
