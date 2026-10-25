"""Central, typed settings object.

Loads `.env` once, resolves the active environment, and exposes everything the
framework needs.  Import the singleton:  ``from config import settings``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from config.environments import Environment, get_environment

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root (does not override real env vars already set,
# so `TEST_ENV=prod pytest` on the CLI still wins).
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    env: Environment
    login_phone: str
    login_password: str
    pharmacy_name: str

    headless: bool
    browser: str
    slow_mo: int
    default_timeout: int
    nav_timeout: int

    run_destructive_tests: bool
    reuse_auth_state: bool

    project_root: Path = PROJECT_ROOT
    screenshots_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "screenshots")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    auth_state_path: Path = field(
        default_factory=lambda: Path(os.getenv("AUTH_STATE") or PROJECT_ROOT / "playwright" / ".auth" / "state.json")
    )
    test_data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "test_data")

    @property
    def base_url(self) -> str:
        return self.env.base_url

    @property
    def is_prod(self) -> bool:
        return self.env.name == "prod"

    @property
    def destructive_allowed(self) -> bool:
        """Destructive tests run only when explicitly enabled AND not on prod."""
        return self.run_destructive_tests and self.env.allow_destructive and not self.is_prod

    def ensure_dirs(self) -> None:
        for d in (
            self.screenshots_dir,
            self.logs_dir,
            self.reports_dir / "allure-results",
            self.auth_state_path.parent,
        ):
            d.mkdir(parents=True, exist_ok=True)


def _build() -> Settings:
    env = get_environment(os.getenv("TEST_ENV", "staging"))
    s = Settings(
        env=env,
        login_phone=os.getenv("LOGIN_PHONE", ""),
        login_password=os.getenv("LOGIN_PASSWORD", ""),
        pharmacy_name=os.getenv("PHARMACY_NAME", "Manik Pharma"),
        headless=_bool("HEADLESS", True),
        browser=os.getenv("BROWSER", "chromium").strip().lower(),
        slow_mo=_int("SLOW_MO", 0),
        default_timeout=_int("DEFAULT_TIMEOUT", 30_000),
        nav_timeout=_int("NAV_TIMEOUT", 45_000),
        run_destructive_tests=_bool("RUN_DESTRUCTIVE_TESTS", False),
        reuse_auth_state=_bool("REUSE_AUTH_STATE", True),
    )
    s.ensure_dirs()
    return s


settings = _build()
