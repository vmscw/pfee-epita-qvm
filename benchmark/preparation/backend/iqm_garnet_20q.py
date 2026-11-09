from benchmark.preparation.backend.scaleway_base import ScalewayProvided


class IQMGarnet20q(ScalewayProvided):
    """Backend relying on the IQM Garnet quantum computer with 20 qubits."""

    def __init__(self):
        super().__init__(backend="QPU-GARNET-20PQ")
        self.name = "iqm-garnet-20q"


__all__ = ["IQMGarnet20q"]
