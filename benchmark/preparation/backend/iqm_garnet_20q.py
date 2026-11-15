from benchmark.preparation.backend.iqm_base import IQMProvided


class IQMGarnet20q(IQMProvided):
    """Backend relying on the IQM Garnet quantum computer with 20 qubits."""

    def __init__(self):
        super().__init__(name="garnet")
        self.name = "iqm-garnet-20q"
        self.num_qubits = 20


__all__ = ["IQMGarnet20q"]
