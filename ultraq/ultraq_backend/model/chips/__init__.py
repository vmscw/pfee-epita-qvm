"""Chips: generic model (`physical_chip.py`) and one class per real chip, built from fetched calibration data.

The fetched calibration snapshot is the source of truth (see `ultraq_backend.model.chips.iqm`).
`CHIPS` maps the chip names used in layout files to their class.
"""

from pathlib import Path

from ultraq_backend.model.chips.iqm import CACHE_ROOT, IQMEmerald, IQMGarnet, snapshots
from ultraq_backend.model.chips.physical_chip import (
    Coupler,
    PhysicalChip,
    Qubit,
    RawMetric,
)

CHIPS: dict[str, type[PhysicalChip]] = {"garnet": IQMGarnet, "emerald": IQMEmerald}
"""Chip name -> class (each has `fetch()` and `load(snapshot, root)`)."""


def load_chip(name: str, snapshot: str = "latest", root: str | Path = CACHE_ROOT) -> PhysicalChip:
    """Build chip `name` from a cached snapshot ("latest" or a timestamp), without network.

    Raises KeyError for an unknown chip, FileNotFoundError if no snapshot is cached.
    """
    if name not in CHIPS:
        raise KeyError(f"unknown chip {name!r}, available: {sorted(CHIPS)}")
    return CHIPS[name].load(snapshot, root)


__all__ = ["CACHE_ROOT", "CHIPS", "Coupler", "IQMEmerald", "IQMGarnet", "PhysicalChip", "Qubit", "RawMetric", "load_chip", "snapshots"]
