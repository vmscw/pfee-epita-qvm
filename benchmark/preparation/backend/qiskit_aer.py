import warnings

import qiskit
import qiskit.qasm2
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.transpiler import CouplingMap
from qiskit_aer import AerJob, AerSimulator

from benchmark.config import invoke_config
from benchmark.utils import qasm2_to_qiskit


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

        self._max_size = config.debug_circuit_max_size
        self._num_shots = config.num_shots

        self._architecture = _define_backend(config.debug_noise_on)
        self._engine = AerSimulator.from_backend(self._architecture)

    def run(self, circuit: str) -> AerJob | None:
        qiskit_circuit = qasm2_to_qiskit(circuit)

        if qiskit_circuit is None:
            return None

        if qiskit_circuit.num_qubits > self._max_size:
            warnings.warn("Circuit contains more than 10 qubits. Ignoring it.")
            return None

        transpiled_circuit = qiskit.transpile(
            qiskit_circuit,
            backend=self._architecture,
        )

        return self._engine.run(transpiled_circuit, shots=self._num_shots)


__all__ = ["QiskitAer"]
