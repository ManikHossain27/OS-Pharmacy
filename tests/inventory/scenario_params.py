"""pytest parameters for the end-to-end scenario matrices (shared by the three inventory modes)."""
from __future__ import annotations

import pytest


def scenario_params(scenarios, *, default_marks: tuple = ()) -> list:
    """One ``pytest.param`` per scenario, id = scenario id; ``smoke``-tagged scenarios carry the smoke mark,
    the others ``default_marks``."""
    return [pytest.param(s, id=s.id, marks=[pytest.mark.smoke] if "smoke" in s.tags else list(default_marks))
            for s in scenarios]
