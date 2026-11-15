from benchmark.preparation.backend.iqm_base import IQMProvided


class IQMEmerald54q(IQMProvided):
    """Backend relying on the IQM Emerald quantum computer with 54 qubits."""

    def __init__(self):
        super().__init__(name="emerald")
        self.name = "iqm-emerald-54q"
        self.num_qubits = 54


__all__ = ["IQMEmerald54q"]
