from iqm.iqm_client import CircuitValidationError
import warnings

from iqm.qiskit_iqm import IQMFakeGarnet
from qiskit import transpile, QuantumCircuit
from qiskit.providers import BackendV2, JobV1

from benchmark.config import invoke_config
from benchmark.utils import qasm2_to_qiskit, SkippedJob


class IQMGarnet20qEmulation:
    """Backend relying on the IQM Garnet quantum computer with 20 qubits.

    This backend is a mock version, which emulates the computer under realistic
    conditions. The engine is run locally, without the need of an API key.
    """

    def __init__(self):
        config = invoke_config()

        self._max_size = config.debug_circuit_max_size
        self._provider = None

        self.name = "iqm-garnet-20q-mock"
        self.num_qubits = 20
        self.architecture: BackendV2 = IQMFakeGarnet()

    def run(self, circuit: QuantumCircuit, shots: int, **kwargs) -> JobV1:
        if circuit.num_qubits > self._max_size:
            reason = f"Circuit contains more than {self._max_size} qubits."
            warnings.warn(f"{reason}. Ignoring it.")
            return SkippedJob(self, reason)

        try:
            return self.architecture.run(circuit, shots=shots, **kwargs)
        except CircuitValidationError as e:
            reason = f"Failed to validate circuit for Garnet backend. Reason: {e}"
            warnings.warn(reason)
            return SkippedJob(self, reason)


__all__ = ["IQMGarnet20qEmulation"]
