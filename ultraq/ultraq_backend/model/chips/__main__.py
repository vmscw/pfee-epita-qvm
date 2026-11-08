"""CLI: `python -m ultraq_backend.model.chips <chip> [--set default] [--out DIR]`.

Fetches the calibration of a chip, caches it and prints a summary of the built chip.
The token is never printed.
"""

from __future__ import annotations

import argparse
import sys

from ultraq_backend.model.chips import CACHE_ROOT, CHIPS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ultraq_backend.model.chips",
        description="Fetch the calibration data of a chip, cache it as JSON and summarize the chip.",
    )
    parser.add_argument("chip", choices=sorted(CHIPS))
    parser.add_argument("--set", dest="calibration_set", default="default",
                        help="calibration set id, or 'default' (default: %(default)s)")
    parser.add_argument("--out", default=str(CACHE_ROOT), help="cache root (default: %(default)s)")
    args = parser.parse_args(argv)

    try:
        chip = CHIPS[args.chip].fetch(args.calibration_set, root=args.out)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (KeyError, ValueError, TypeError) as exc:
        print(f"error: unexpected calibration data from the API: {exc!r}", file=sys.stderr)
        return 1

    inactive = [chip.qubit(i).label for i in range(chip.num_qubits) if not chip.qubit(i).active]
    print(f"{chip.name} snapshot {chip.snapshot} (calibration set {chip.calibration_set_id})")
    print(
        f"  {chip.num_qubits} qubits ({len(chip.active_qubits)} active, inactive: {inactive}), "
        f"{chip.num_couplers} couplers ({len(chip.active_couplers)} active)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
