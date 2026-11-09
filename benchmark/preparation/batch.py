from collections.abc import Iterable, Iterator, Sequence


class Batch(Sequence):
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

        self._length: int = len(self.names)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return zip(self.names, self.circuits)

    def __len__(self) -> int:
        return self._length

    def __getitem__(
        self, index: int | slice[int | None, int | None, int | None]
    ) -> tuple[str, str] | tuple[tuple[str, str], ...]:
        if isinstance(index, int):
            return self.names[index], self.circuits[index]

        return tuple(zip(self.names[index], self.circuits[index]))

    def get(self, i: int) -> tuple[str, str]:
        """Return the case name and circuit at index i.

        Args:
            i (int): an index

        Returns:
            a tuple containing sequentually the name and the circuit of the
            batch case

        Raises:
            ValueError: if index is invalid
        """
        if abs(i - 1) > self._length:
            raise IndexError

        return self.names[i], self.circuits[i]


__all__ = [
    "Batch",
]
