from abc import ABC

from iqm.qiskit_iqm import IQMBackend, IQMJob, IQMProvider
from iqm.qiskit_iqm.iqm_backend import IQMBackendBase
from qiskit import transpile
from qiskit.providers import JobV1

from benchmark.config import invoke_config, invoke_auth_config
from benchmark.utils import qasm2_to_qiskit


class IQMProvided(ABC):
    """Abstract structure for any backend provided by IQM.

    Args:
        name (str): name of the computer to invoke from the IQM provider
    """

    def __init__(self, name: str):
        config = invoke_config()
        auth_config = invoke_auth_config()

        self._num_shots = config.num_shots
        self._provider: IQMProvider | None = IQMProvider(
            url=auth_config.IQM_SERVER_URL + name,
            quantum_computer=name,
            token=auth_config.IQM_TOKEN,
        )
        self._engine: IQMBackendBase = self._provider.get_backend()
        self.name: str = "iqm-generic"

    def run(self, circuit: str) -> JobV1 | None:
        compiled_circuit = qasm2_to_qiskit(circuit)

        if compiled_circuit is None:
            return None

        # FIXME: remove this. schedulers want to do their own transpilation
        transpiled_circuit = transpile(compiled_circuit, self._engine)
        return self._engine.run(transpiled_circuit, shots=self._num_shots)


__all__ = ["IQMProvided"]
