from benchmark.preparation.backend.scaleway_base import ScalewayProvided


class IQMEmerald54q(ScalewayProvided):
    """Backend relying on the IQM Emerald quantum computer with 54 qubits."""

    def __init__(self):
        super().__init__(backend="QPU-EMERALD-54PQ")


__all__ = ["IQMEmerald54q"]
