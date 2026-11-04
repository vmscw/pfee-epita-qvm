from collections.abc import Iterable, Sized


class Batch(Sized):
    """A batch of grouped circuits.

    Args:
        names (Iterable[str]): an iteration of case names
        circuits (Iterable[str]): an iteration of case circuits. A circuit is
                                  always specified in OpenQASM format

    Raises:
        AssertionError: names does not have the same size as circuits
    """

    def __init__(self, names: Iterable[str], circuits: Iterable[str]):
        self.names: list[str] = list(iter(names))
        self.circuits: list[str] = list(iter(circuits))

        assert len(self.names) == len(self.circuits), (
            "names and circuits have an inconsistent length: names has a "
            f"length of {len(self.names)} while circuits has a length of "
            f"{len(self.circuits)}"
        )

    def __len__(self) -> int:
        return len(self.names)


__all__ = [
    "Batch",
]
