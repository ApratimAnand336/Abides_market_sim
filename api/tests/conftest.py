"""Test configuration for api/tests: the `slow` marker (spec v1.3 §7.6).

Slow tests (the realism-lab regression set, 9 full days) are skipped unless
selected explicitly: python -m pytest api/tests -m slow"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long-running (full-day simulations); run with -m slow")


def pytest_collection_modifyitems(config, items):
    if "slow" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="slow test: run with -m slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
