from typing import Any

import polars as pl


type Record = dict[str, Any]
type BenchmarkDatabase = list[Record]

runtime_results: BenchmarkDatabase = []
circuits_results: BenchmarkDatabase = []
counts_per_circuits: BenchmarkDatabase = []

__all__ = [
    "BenchmarkDatabase",
    "Record",
    "circuits_results",
    "counts_per_circuits",
    "runtime_results",
]
