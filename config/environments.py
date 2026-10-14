"""Per-environment base URLs and metadata.

`TEST_ENV` (local | staging | prod) selects which block is active.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Environment:
    name: str
    base_url: str
    # Production is protected: destructive tests never run here regardless of flags.
    allow_destructive: bool


def _clean(url: str | None) -> str:
    return (url or "").strip().rstrip("/") + "/" if url else ""


ENVIRONMENTS: dict[str, Environment] = {
    "local": Environment(
        name="local",
        base_url=_clean(os.getenv("LOCAL_BASE_URL", "http://localhost:3000")),
        allow_destructive=True,
    ),
    "staging": Environment(
        name="staging",
        base_url=_clean(os.getenv("STAGING_BASE_URL", "https://pms-sql-portal.ems24.co/")),
        allow_destructive=True,
    ),
    "prod": Environment(
        name="prod",
        base_url=_clean(os.getenv("PROD_BASE_URL", "")),
        allow_destructive=False,
    ),
}


def get_environment(env_name: str) -> Environment:
    key = (env_name or "staging").strip().lower()
    if key not in ENVIRONMENTS:
        raise ValueError(
            f"Unknown TEST_ENV={env_name!r}. Expected one of {sorted(ENVIRONMENTS)}."
        )
    env = ENVIRONMENTS[key]
    if not env.base_url:
        raise ValueError(
            f"No base URL configured for TEST_ENV={key!r}. "
            f"Set {key.upper()}_BASE_URL in your .env."
        )
    return env
