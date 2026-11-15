import warnings

from qiskit_scaleway.backends.base_job import BaseJob

from benchmark.config import invoke_config
from benchmark.preparation.backend.scaleway_base import ScalewayProvided
from benchmark.utils import qasm2_to_qiskit


# NOTE: we will keep this in case we want to debug interactions with Scaleway,
#       but by nature it is not defined very well (ex: num_qubits is incorrect).
#       it is best not to utilize this backend for actual benchmarking
class QiskitAerScaleway(ScalewayProvided):
    """Qiskit AER-based backend running on Scaleway HPC servers.

    We use this backend to experiment proper functionning of the benchmark when
    iteracting with a third-party backend.
    """

    def __init__(self):
        super().__init__(backend="EMU-AER-H100")

        config = invoke_config()

        self._max_size = config.debug_circuit_max_size

        self.num_qubits = 25
        self.name = "qiskit-aer-scaleway"

    def run(self, circuit: str) -> BaseJob | None:
        qiskit_circuit = qasm2_to_qiskit(circuit)

        if qiskit_circuit is None:
            return None

        if qiskit_circuit.num_qubits > self._max_size:
            warnings.warn(
                f"Circuit contains more than {self._max_size} qubits. Ignoring it."
            )
            return None

        return super().run(circuit)



__all__ = ["QiskitAerScaleway"]
