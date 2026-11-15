from iqm.iqm_client import CircuitValidationError
import warnings

from iqm.qiskit_iqm import IQMFakeGarnet
from qiskit import transpile
from qiskit.providers.job import JobV1

from benchmark.config import invoke_config
from benchmark.utils import qasm2_to_qiskit


class IQMGarnet20qEmulation:
    """Backend relying on the IQM Garnet quantum computer with 20 qubits.

    This backend is a mock version, which emulates the computer under realistic
    conditions. The engine is run locally, without the need of an API key.
    """

    def __init__(self):
        config = invoke_config()

        self._max_size = config.debug_circuit_max_size
        self._num_shots = config.num_shots

        self._provider = None
        self._engine = IQMFakeGarnet()

        self.name = "iqm-garnet-20q-mock"
        self.num_qubits = 20

    def run(self, circuit: str) -> JobV1 | None:
        qiskit_circuit = qasm2_to_qiskit(circuit)

        if qiskit_circuit is None:
            return None

        if qiskit_circuit.num_qubits > self._max_size:
            warnings.warn(
                f"Circuit contains more than {self._max_size} qubits. Ignoring it."
            )
            return None

        try:
            # FIXME: remove this. schedulers want to do their own transpilation
            transpiled_circuit = transpile(qiskit_circuit, self._engine)
            return self._engine.run(transpiled_circuit, shots=self._num_shots)
        except CircuitValidationError as e:
            warnings.warn(
                f"Failed to validate circuit for Garnet backend. Reason: {e}"
            )


__all__ = ["IQMGarnet20qEmulation"]
