import os

import pytest


def pytest_configure(config):
	config.addinivalue_line("markers", "alone: uses the whole machine (rig.py looks at every process on it, and its CPU "
		"and disk load), so it runs with no other test beside it: not on pytest-xdist's workers")


def pytest_collection_modifyitems(config, items):
	# Run in parallel (pytest -n, pytest-xdist), the other workers are Python processes that the 'alone' tests' rig.py
	# would see as foreign GPU users (on Windows every python.exe counts) and as CPU load. There they are skipped; run
	# them on one worker: pytest tests
	if not os.environ.get("PYTEST_XDIST_WORKER"):
		return
	skip = pytest.mark.skip(reason="runs alone, not beside other tests: pytest -m alone tests")
	for item in items:
		if item.get_closest_marker("alone"):
			item.add_marker(skip)
