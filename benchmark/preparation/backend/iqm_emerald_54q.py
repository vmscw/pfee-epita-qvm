from benchmark.preparation.backend.iqm_base import IQMBase


class IQMEmerald54q(IQMBase):
    """Backend relying on the IQM Emerald quantum computer with 54 qubits."""

    def __init__(self):
        super().__init__(computer="QPU-EMERALD-54PQ")


__all__ = ["IQMEmerald54q"]
