from qiskit.providers.backend import BackendV2
import warnings

import qiskit
import qiskit.qasm2
from qiskit import QuantumCircuit
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.transpiler import CouplingMap
from qiskit_aer import AerJob, AerSimulator

from benchmark.config import invoke_config
from benchmark.utils import SkippedJob, qasm2_to_qiskit


def _define_backend(noise: bool = False) -> GenericBackendV2:
    """Define a fake backend architecture.

    In this case, the architecture is a grid of qubits of size 5x5.

    Args:
        noise (bool): if true, the returned backend will have realistic noise

    Returns:
        GenericBackendV2: A simulator backend with a grid architecture of 25
                          qubits.
    """
    architecture = CouplingMap.from_grid(5, 5)

    return GenericBackendV2(
        num_qubits=architecture.size(),
        coupling_map=architecture,
        noise_info=noise,
    )


class QiskitAer:
    """Backend relying on the regular Qiskit Aer simulator.

    To illustrate something realistic, the connectivity of the simulator is not
    infinite, but rather based on a defined architecture of 25 qubits.

    Beyond it being potential target for benchmarking, this backend is mostly
    used internally for debugging.
    """

    def __init__(self):
        config = invoke_config()

        self.architecture: BackendV2 = _define_backend(config.debug_noise_on)

        self._max_size = config.debug_circuit_max_size
        self._engine = AerSimulator.from_backend(self.architecture)

        self.name = "qiskit_aer"
        self.num_qubits = 25

    def run(self, circuit: QuantumCircuit, shots: int, **kwargs) -> AerJob | SkippedJob:
        if circuit.num_qubits > self._max_size:
            reason = f"Circuit contains more than {self._max_size} qubits."
            warnings.warn(f"{reason}. Ignoring it.")
            return SkippedJob(self, reason)

        return self._engine.run(circuit, shots, **kwargs)


__all__ = ["QiskitAer"]
