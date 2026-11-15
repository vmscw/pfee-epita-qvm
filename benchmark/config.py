import functools
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global configuration to use as reference for the benchmark."""

    model_config = SettingsConfigDict(cli_parse_args=True, frozen=True)

    benchmark_name: str | None = None
    """Name to apply to the benchmark.

    Defaults to f"{scheduler}_{backend}_{timestamp}".
    """
    artefacts_dir: Path = Path(".") / "artefacts"
    """Folder at which to store outputs."""

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


class AuthConfig(BaseSettings):
    """Global configuration to use when connecting to external APIs."""

    model_config = SettingsConfigDict(env_file=".env", frozen=True)

    SCW_PROJECT_ID: str = ""
    """Scaleway project ID. Only accessed when using a Scaleway backend."""
    SCW_SECRET_KEY: str = ""
    """Scaleway project ID. Only accessed when using a Scaleway backend."""


@functools.lru_cache()
def invoke_config() -> Config:
    """Return the configuration of the benchmark runtime.

    The runtime configuration is meant to be used as a read-only singleton.

    Returns:
        Config: the configuration singleton
    """
    return Config()


@functools.lru_cache()
def invoke_auth_config() -> AuthConfig:
    """Return authentication credentials.

    The runtime configuration is meant to be used as a read-only singleton.

    Returns:
        Config: the configuration singleton
    """
    return AuthConfig()


__all__ = [
    "AuthConfig",
    "Config",
    "invoke_config",
    "invoke_auth_config",
]
