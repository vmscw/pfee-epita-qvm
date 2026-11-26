"""Processing steps, each turning one representation (`ultraq_backend.model`) into the next.

In the order a job goes through them:

- `validation`: circuit + target graph -> accepted or ValueError;
- `scheduler`: queue of `Job` -> `Decision` (job, VMs);
- `mapping`: `Decision` + `ChipLayout` -> `PlacedJob` (physical qubits);
- `executor`: batch of `PlacedJob` -> counts per job.

The `Hypervisor` chains them.
"""
