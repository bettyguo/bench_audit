"""User-facing configuration via env or .env file."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BENCH_AUDIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cache_dir: Path = Field(
        default_factory=lambda: user_cache_path("bench-audit"),
        description="Where eval-set artifacts and Inspect AI caches live.",
    )
    results_dir: Path = Field(
        default=Path("_results"),
        description="Where ProbeResult JSONL records are written.",
    )
    allow_network: bool = Field(
        default=True,
        description="If False, refuses any HTTP fetch; offline mode for CI.",
    )
    default_ci_half_width: float = Field(
        default=0.1,
        description="Probes refuse a non-inconclusive verdict if CI half-width exceeds this.",
    )


settings = Settings()
