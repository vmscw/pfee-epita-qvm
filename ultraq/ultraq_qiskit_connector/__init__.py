"""Qiskit interface of ultraq: provider, virtual backends (BackendV2), job (JobV1).

    from qiskit import transpile
    from ultraq_backend import Hypervisor
    from ultraq_backend.model.chips import load_chip
    from ultraq_qiskit_connector import UltraqProvider

    hv = Hypervisor(load_chip("garnet"))             # the whole chip as one VM "chip"
    backend = UltraqProvider(hv).get_backend("chip")
    counts = backend.run(transpile(qc, backend)).result().get_counts()

This package sits on top of the `ultraq_backend` core: it only uses a `Hypervisor` object
(`submit`, `status`, `result`, and `virtual_topology` for `graph`, `target`,
`categories`, `fusion_candidates`). The core never imports it.
"""

from ultraq_backend.log import setup_logging

setup_logging()  # also configures this package's logger (idempotent)

from ultraq_qiskit_connector.backend import CategoryBackend, FusedBackend  # noqa: E402
from ultraq_qiskit_connector.job import UltraqJob  # noqa: E402
from ultraq_qiskit_connector.provider import UltraqProvider  # noqa: E402

__all__ = ["CategoryBackend", "FusedBackend", "UltraqJob", "UltraqProvider"]
