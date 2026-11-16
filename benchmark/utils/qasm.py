import warnings

import qiskit.qasm2
from qiskit import QuantumCircuit


CONVERSION_FAILURE_WARNING_FORMAT = (
    "Circuit is invalid. Consider fixing it or removing it from the benchmark. Reason: {}"
)


def qasm2_to_qiskit(circuit: str) -> QuantumCircuit | None:
    """Convert a QASM2 quantum program to a Qiskit circuit.

    If conversion fails, fail gracefully and return None.

    Args:
        circuit (str): a circuit in OpenQASM2 format

    Returns:
        QuantumCircuit | None: the matching Qiskit circuit if conversion
                               succeeded. None otherwise
    """
    try:
        return qiskit.qasm2.loads(circuit)
    except qiskit.qasm2.exceptions.QASM2ParseError as e:
        warnings.warn(CONVERSION_FAILURE_WARNING_FORMAT.format(e))
        return None


__all__ = ["qasm2_to_qiskit"]
