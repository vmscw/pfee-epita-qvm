import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global configuration to use as reference for the benchmark."""

    model_config = SettingsConfigDict(cli_parse_args=True, frozen=True)

    backend: str
    """Backend to use for the benchmark."""
    scheduler: str
    """Scheduler to measure for the benchmark."""

    num_shots: int = 1024
    """Number of shots run for each circuit."""
    seed: int = 42
    """Seed to use for the benchmark."""

    debug_circuit_max_size: int = 12
    """When using a simulator, the max size accepted for input circuits.

    Any circuit bigger than the specified size will be ignored.
    """
    debug_noise_on: bool = False
    """When using a simulator, whether to add noise to the backend."""


@functools.lru_cache()
def invoke_config() -> Config:
    """Return the configuration of the benchmark runtime.

    The runtime configuration is meant to be used as a read-only singleton.

    Returns:
        Config: the configuration singleton
    """
    return Config()


__all__ = [
    "Config",
    "invoke_config",
]
