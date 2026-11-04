from benchmark.preparation.backend.iqm_base import IQMBase


class IQMGarnet20qEmulation(IQMBase):
    """Backend relying on the IQM Garnet quantum computer with 20 qubits.

    This backend is a mock version, which emulates the computer under realistic
    conditions. The processing is still ensured by the IQM API.
    """

    def __init__(self):
        super().__init__(computer="QPU-GARNET-20PQ-MOCK")


__all__ = ["IQMGarnet20qEmulation"]
