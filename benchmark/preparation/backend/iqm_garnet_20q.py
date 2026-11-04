from benchmark.preparation.backend.iqm_base import IQMBase


class IQMGarnet20q(IQMBase):
    """Backend relying on the IQM Garnet quantum computer with 20 qubits."""

    def __init__(self):
        super().__init__(computer="QPU-GARNET-20PQ")


__all__ = ["IQMGarnet20q"]
