from benchmark.preparation.backend.scaleway_base import ScalewayProvided


class IQMGarnet20qEmulation(ScalewayProvided):
    """Backend relying on the IQM Garnet quantum computer with 20 qubits.

    This backend is a mock version, which emulates the computer under realistic
    conditions. The processing is still ensured by IQM.
    """

    def __init__(self):
        super().__init__(backend="QPU-GARNET-20PQ-MOCK")
        self.name = "iqm-garnet-20q-mock"


__all__ = ["IQMGarnet20qEmulation"]
