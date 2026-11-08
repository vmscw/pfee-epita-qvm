"""IQM chips (Garnet, Emerald): fetch their calibration from IQM Resonance, cache it, build a `PhysicalChip`.

This is the only module that knows IQM: the Resonance REST API, the cache
layout, the dynamic quantum architecture (DQA) and the `dut_field` names of
the raw values. It must not know the hypervisor, the layouts or the scheduling.

The fetched snapshot is the source of truth: qubits, couplers, which of them
are active and all calibration values come from it.

    chip = IQMGarnet.fetch()                       # API -> cache -> PhysicalChip
    chip = IQMGarnet.load()                        # latest cached snapshot, no network
    chip = IQMGarnet.load("20261108T115135Z")      # a given snapshot

Snapshot -> PhysicalChip:

- nodes: DQA `qubits`, in order (QB1 -> 0); a qubit is active if the DQA
  offers both `prx` and `measure` on it;
- edges: every physical coupler, i.e. every `cz` locus of the DQA and every
  `TC-a-b` (tunable coupler) label of the calibration set; a coupler is active
  if the DQA offers `cz` on it;
- every value of `metrics.json` and `calibration_set.json` is kept
  (`RawMetric`) on its coupler (two qubit labels or a `TC-a-b` label), on its
  qubit (one label) or on the chip (anything else);
- typed values from `metrics.json` (non-invalid values only): T1, T2
  (Ramsey `t2_time`), fidelity of `prx` (-> "r") and `measure` per qubit, of
  `cz` per pair. Everything else (e.g. `t2_echo_time`) stays in `raw_metrics`.

Cache: `<root>/<qpu>/<UTC timestamp>/{calibration_set,metrics,dynamic_quantum_architecture,meta}.json`,
root = `calibration_data/` at the project root by default (gitignored).
The token comes from the argument, else `IQM_TOKEN` (a `.env` file at or above
the current directory is loaded first); it never appears in an error message.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import rustworkx as rx
from dotenv import find_dotenv, load_dotenv

from ultraq_backend.model.chips.physical_chip import (
    Coupler,
    PhysicalChip,
    Qubit,
    RawMetric,
)

BASE_URL = "https://resonance.iqm.tech/api/v1"
TOKEN_ENV = "IQM_TOKEN"
USER_AGENT = "ultraq/0.1"
"""Sent explicitly: the API's firewall answers 403 to urllib's default "Python-urllib/3.x"."""

CACHE_ROOT = Path(__file__).resolve().parents[3] / "calibration_data"
"""Default cache root: `calibration_data/` at the project root (independent of the cwd)."""

GATES = {"prx": "r", "cz": "cz"}
"""IQM native gates -> Qiskit names (DQA gates without a Qiskit equivalent are not native gates)."""

SYMMETRIC_GATES = {"cz"}

_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_QB = re.compile(r"QB\d+")
_TC = re.compile(r"TC-(\d+)-(\d+)")


# ---------------------------------------------------------------- HTTP


class _NotFound(RuntimeError):
    """The server answered 404: an error, except for the metrics endpoint where it is tolerated."""


def _get_json(url: str, token: str, timeout: float):
    """GET `url` with the Bearer token and decode its JSON body (no message ever contains the token)."""
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise _NotFound(f"IQM API error: HTTP 404 ({exc.reason}) on GET {url}") from None
        raise RuntimeError(f"IQM API error: HTTP {exc.code} ({exc.reason}) on GET {url}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"IQM API unreachable: {exc.reason} on GET {url}") from None
    except TimeoutError:
        raise RuntimeError(f"IQM API timeout after {timeout}s on GET {url}") from None
    try:
        return json.loads(body)
    except ValueError:
        raise RuntimeError(f"IQM API returned non-JSON content on GET {url}") from None


def _resolve_token(token: str | None) -> str:
    if token:
        return token
    load_dotenv(find_dotenv(usecwd=True))
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"No IQM token: set the {TOKEN_ENV} environment variable "
            f"or put {TOKEN_ENV}=... in a .env file at or above the current directory."
        )
    return token


def _fetch_raw(qpu: str, calibration_set: str, token: str | None, timeout: float) -> dict:
    """Calibration set, metrics (None on 404) and DQA of `qpu`, raw, plus fetch metadata."""
    token = _resolve_token(token)
    base = (
        f"{BASE_URL}/calibration-sets/"
        f"{urllib.parse.quote(qpu, safe='')}/{urllib.parse.quote(calibration_set, safe='')}"
    )
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cal = _get_json(base, token, timeout)
    try:
        metrics = _get_json(f"{base}/metrics", token, timeout)
    except _NotFound:
        warnings.warn(
            f"No quality metrics for calibration set {calibration_set!r} of {qpu!r} (HTTP 404).",
            stacklevel=3,
        )
        metrics = None
    dqa = _get_json(f"{base}/dynamic-quantum-architecture", token, timeout)
    return {
        "meta": {"qpu": qpu, "requested_set": calibration_set, "fetched_at": fetched_at},
        "calibration_set": cal,
        "metrics": metrics,
        "dynamic_quantum_architecture": dqa,
    }


# ---------------------------------------------------------------- cache


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _save(raw: dict, root: str | Path) -> Path:
    """Write a fetched snapshot to `<root>/<qpu>/<timestamp>/`; return that directory."""
    meta = raw["meta"]
    stamp = datetime.fromisoformat(meta["fetched_at"]).astimezone(timezone.utc).strftime(_TIMESTAMP_FORMAT)
    directory = Path(root) / meta["qpu"] / stamp
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "calibration_set.json", raw["calibration_set"])
    _write_json(directory / "dynamic_quantum_architecture.json", raw["dynamic_quantum_architecture"])
    if raw["metrics"] is not None:
        _write_json(directory / "metrics.json", raw["metrics"])
    _write_json(directory / "meta.json", {**meta, "has_metrics": raw["metrics"] is not None})
    return directory


def snapshots(qpu: str, root: str | Path = CACHE_ROOT) -> list[str]:
    """Identifiers (timestamps) of the cached snapshots of `qpu`, oldest first."""
    qpu_dir = Path(root) / qpu
    if not qpu_dir.is_dir():
        return []
    return sorted(d.name for d in qpu_dir.iterdir() if (d / "meta.json").is_file())


def _snapshot_dir(qpu: str, snapshot: str, root: str | Path) -> Path:
    """Directory of a cached snapshot ("latest" = most recent); FileNotFoundError if absent."""
    available = snapshots(qpu, root)
    if not available:
        raise FileNotFoundError(
            f"No cached calibration for {qpu!r} under {Path(root) / qpu}: "
            f"run `python -m ultraq_backend.model.chips {qpu}` first."
        )
    name = available[-1] if snapshot == "latest" else snapshot
    if name not in available:
        raise FileNotFoundError(f"No snapshot {snapshot!r} for {qpu!r}; cached: {available}")
    return Path(root) / qpu / name


def _read(directory: Path) -> dict:
    """Read back a cached snapshot (same shape as `_fetch_raw` returns)."""

    def load(name: str):
        path = directory / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    return {
        "meta": load("meta"),
        "calibration_set": load("calibration_set"),
        "metrics": load("metrics"),
        "dynamic_quantum_architecture": load("dynamic_quantum_architecture"),
    }


# ---------------------------------------------------------------- snapshot -> PhysicalChip


def _build_chip(cls: type[PhysicalChip], chip_id: str, name: str, snapshot: str, raw: dict) -> PhysicalChip:
    """Build a `cls` instance from a raw snapshot (see the module docstring)."""
    dqa = raw["dynamic_quantum_architecture"]
    gates = dqa["gates"]
    impl = {g: v["default_implementation"] for g, v in gates.items()}
    loci = {g: [tuple(locus) for locus in v["implementations"][impl[g]]["loci"]] for g, v in gates.items()}
    cal_obs = (raw["calibration_set"] or {}).get("observations", [])
    metric_obs = (raw["metrics"] or {}).get("observations", [])

    # Qubits: every DQA qubit; active if prx and measure are offered on it.
    labels = list(dqa["qubits"])
    index = {label: i for i, label in enumerate(labels)}
    with_prx = {locus[0] for locus in loci.get("prx", [])}
    with_measure = {locus[0] for locus in loci.get("measure", [])}
    qubits = [Qubit(label, active=label in with_prx and label in with_measure) for label in labels]

    # Couplers: cz loci (DQA direction) + TC-a-b labels of the calibration set.
    pairs: dict[frozenset[int], tuple[int, int]] = {}
    with_cz: set[frozenset[int]] = set()
    for locus in loci.get("cz", []):
        a, b = index[locus[0]], index[locus[1]]
        pairs.setdefault(frozenset((a, b)), (a, b))
        with_cz.add(frozenset((a, b)))
    for obs in cal_obs:
        for x, y in _TC.findall(obs["dut_field"]):
            if f"QB{x}" in index and f"QB{y}" in index:
                a, b = index[f"QB{x}"], index[f"QB{y}"]
                pairs.setdefault(frozenset((a, b)), (a, b))

    graph = rx.PyGraph()
    graph.add_nodes_from(qubits)
    couplers: dict[frozenset[int], Coupler] = {}
    for key, (a, b) in sorted(pairs.items(), key=lambda kv: sorted(kv[1])):
        couplers[key] = Coupler(active=key in with_cz)
        graph.add_edge(a, b, couplers[key])

    chip = cls(
        id=chip_id,
        name=name,
        vendor="IQM",
        native_gates={g: q for g, q in GATES.items() if g in gates},
        symmetric_gates=set(SYMMETRIC_GATES),
        graph=graph,
        snapshot=snapshot,
        calibration_set_id=dqa.get("calibration_set_id"),
        gate_loci=loci,
    )

    # Every raw value, attached to its coupler, qubit or the chip.
    for source, entries in (("calibration_set", cal_obs), ("metrics", metric_obs)):
        for o in entries:
            rm = RawMetric(
                name=o["dut_field"],
                value=o["value"],
                unit=o.get("unit") or "",
                source=source,
                extra={k: v for k, v in o.items() if k not in ("dut_field", "value", "unit")},
            )
            dut = o["dut_field"]
            tc = _TC.findall(dut)
            qbs = [q for q in dict.fromkeys(_QB.findall(dut)) if q in index]
            key = None
            if tc:
                x, y = tc[0]
                if f"QB{x}" in index and f"QB{y}" in index:
                    key = frozenset((index[f"QB{x}"], index[f"QB{y}"]))
            elif len(qbs) == 2:
                key = frozenset(index[q] for q in qbs)
            if key is not None and key in couplers:
                couplers[key].raw_metrics.append(rm)
            elif not tc and len(qbs) == 1:
                qubits[index[qbs[0]]].raw_metrics.append(rm)
            else:
                chip.raw_metrics.append(rm)

    # Typed values from the metrics (default implementations only, invalid skipped).
    qubit_metrics = {
        "t1": re.compile(r"characterization\.model\.(QB\d+)\.t1_time$"),
        "t2": re.compile(r"characterization\.model\.(QB\d+)\.t2_time$"),
    }
    fidelity_1q = {}
    if "prx" in impl:
        fidelity_1q["r"] = re.compile(rf"metrics\.rb\.prx\.{re.escape(impl['prx'])}\.(QB\d+)\.fidelity:par=d2$")
    if "measure" in impl:
        fidelity_1q["measure"] = re.compile(
            rf"metrics\.ssro\.measure\.{re.escape(impl['measure'])}\.(QB\d+)\.fidelity$"
        )
    fidelity_cz = (
        re.compile(rf"metrics\.irb\.cz\.{re.escape(impl['cz'])}\.(QB\d+)__(QB\d+)\.fidelity:par=d2$")
        if "cz" in impl
        else None
    )
    for o in metric_obs:
        if o.get("invalid"):
            continue
        dut, value = o["dut_field"], o["value"]
        for attr, pattern in qubit_metrics.items():
            m = pattern.match(dut)
            if m and m.group(1) in index:
                setattr(qubits[index[m.group(1)]], attr, value)
        for gate, pattern in fidelity_1q.items():
            m = pattern.match(dut)
            if m and m.group(1) in index:
                qubits[index[m.group(1)]].gate_fidelity[gate] = value
        m = fidelity_cz.match(dut) if fidelity_cz else None
        if m and m.group(1) in index and m.group(2) in index:
            key = frozenset((index[m.group(1)], index[m.group(2)]))
            if key in couplers:
                couplers[key].gate_fidelity["cz"] = value
    return chip


# ---------------------------------------------------------------- chips


@dataclass
class IQMGarnet(PhysicalChip):
    """IQM Garnet (20 qubits, square lattice), built from a Resonance calibration snapshot.

    calibration_set_id: IQM id of the calibration set in use (same id for two
        snapshots fetched without a recalibration in between).
    gate_loci: the DQA as is, {IQM gate name: [locus as a tuple of IQM labels]}
        for the default implementation of every gate, including gates without
        a Qiskit equivalent (prx_12, measure_012, cc_prx, reset_wait...).
    """

    calibration_set_id: str | None = None
    gate_loci: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)

    @classmethod
    def fetch(
        cls,
        calibration_set: str = "default",
        token: str | None = None,
        root: str | Path = CACHE_ROOT,
        timeout: float = 30.0,
    ) -> IQMGarnet:
        """Fetch the calibration from Resonance, cache it under `root`, build the chip.

        Raises RuntimeError on any HTTP or network failure (the metrics 404 only warns).
        """
        raw = _fetch_raw("garnet", calibration_set, token, timeout)
        directory = _save(raw, root)
        return _build_chip(cls, "garnet", "IQM Garnet", directory.name, raw)

    @classmethod
    def load(cls, snapshot: str = "latest", root: str | Path = CACHE_ROOT) -> IQMGarnet:
        """Build the chip from a cached snapshot ("latest" or a timestamp), without network.

        Raises FileNotFoundError if there is no such snapshot.
        """
        directory = _snapshot_dir("garnet", snapshot, root)
        return _build_chip(cls, "garnet", "IQM Garnet", directory.name, _read(directory))


@dataclass
class IQMEmerald(PhysicalChip):
    """IQM Emerald (54 qubits, square lattice), built from a Resonance calibration snapshot.

    calibration_set_id: IQM id of the calibration set in use (same id for two
        snapshots fetched without a recalibration in between).
    gate_loci: the DQA as is, {IQM gate name: [locus as a tuple of IQM labels]}
        for the default implementation of every gate, including gates without
        a Qiskit equivalent (prx_12, measure_012, cc_prx, reset_wait...).
    """

    calibration_set_id: str | None = None
    gate_loci: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)

    @classmethod
    def fetch(
        cls,
        calibration_set: str = "default",
        token: str | None = None,
        root: str | Path = CACHE_ROOT,
        timeout: float = 30.0,
    ) -> IQMEmerald:
        """Fetch the calibration from Resonance, cache it under `root`, build the chip.

        Raises RuntimeError on any HTTP or network failure (the metrics 404 only warns).
        """
        raw = _fetch_raw("emerald", calibration_set, token, timeout)
        directory = _save(raw, root)
        return _build_chip(cls, "emerald", "IQM Emerald", directory.name, raw)

    @classmethod
    def load(cls, snapshot: str = "latest", root: str | Path = CACHE_ROOT) -> IQMEmerald:
        """Build the chip from a cached snapshot ("latest" or a timestamp), without network.

        Raises FileNotFoundError if there is no such snapshot.
        """
        directory = _snapshot_dir("emerald", snapshot, root)
        return _build_chip(cls, "emerald", "IQM Emerald", directory.name, _read(directory))
