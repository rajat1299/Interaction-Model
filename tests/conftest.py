"""Pytest config for the empty scaffold (WP0).

Pytest exits 5 when no tests are collected; WP0 acceptance requires exit 0
with zero collected tests. Once real tests land, this only remaps that case.
"""


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 5:  # no tests collected
        session.exitstatus = 0
