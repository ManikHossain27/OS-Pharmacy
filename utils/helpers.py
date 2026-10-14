"""Small shared helpers: secret masking, evidence capture, retries."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import allure
from playwright.sync_api import Page

from config import settings
from utils.logger import get_logger

log = get_logger("helpers")


def mask_secret(value: str, keep: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def screenshot(page: Page, name: str, attach: bool = True) -> Path:
    settings.screenshots_dir.mkdir(parents=True, exist_ok=True)
    path = settings.screenshots_dir / f"{name}_{timestamp()}.png"
    page.screenshot(path=str(path), full_page=True)
    if attach:
        allure.attach.file(
            str(path), name=name, attachment_type=allure.attachment_type.PNG
        )
    return path


def attach_text(name: str, content: str) -> None:
    allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_page_context(page: Page, label: str = "page-context") -> None:
    """Attach URL + visible text snapshot + console-free DOM hints to Allure."""
    try:
        ctx = {
            "url": page.url,
            "title": page.title(),
            "viewport": page.viewport_size,
        }
        attach_text(f"{label}-meta", json.dumps(ctx, indent=2))
        body = page.locator("body").inner_text(timeout=2_000)
        attach_text(f"{label}-visible-text", body[:5_000])
    except Exception as exc:  # pragma: no cover - best-effort evidence
        log.warning("attach_page_context failed: %s", exc)


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def money(text: str) -> float:
    """Parse a UI money/number string ("Tk 1,234.50", "-Tk 5", "10%", "7") to float.

    Takes the FIRST number in the text (sign-aware), so "Tk 90.00 (10%)" -> 90.0.
    """
    import re
    m = re.search(r"(-)?\s*(?:Tk\.?|৳)?\s*(-)?(\d[\d,]*\.?\d*|\.\d+)", text or "")
    if not m:
        raise ValueError(f"no number found in {text!r}")
    value = float(m.group(3).replace(",", ""))
    return -value if (m.group(1) or m.group(2)) else value


def numbers_in(text: str) -> list[float]:
    """Every number found in ``text`` (commas stripped)."""
    import re
    return [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", text or "")]
