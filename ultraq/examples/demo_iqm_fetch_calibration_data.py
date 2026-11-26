"""Fetch the calibration data of the IQM chips (Garnet and Emerald) and cache it.

Each fetch writes a snapshot under `CACHE_ROOT/<chip>/<timestamp>/`; layouts
and `IQMGarnet.load()` / `IQMEmerald.load()` then use the latest one, offline.

Needs IQM_URL and IQM_CALIBRATION_TOKEN (environment or .env).
From the project root `ultraq/`:

    uv run python examples/demo_iqm_fetch_calibration_data.py
"""

from ultraq_backend.model.chips import CACHE_ROOT, IQMEmerald, IQMGarnet

for chip_class in (IQMGarnet, IQMEmerald):
    chip = chip_class.fetch()
    print(
        f"{chip.name}: snapshot {chip.snapshot}, "
        f"{len(chip.active_qubits)}/{chip.num_qubits} active qubits, "
        f"{len(chip.active_couplers)}/{chip.num_couplers} active couplers"
    )

print(f"cached under {CACHE_ROOT}")
