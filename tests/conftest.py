import contextlib, os, subprocess

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


@contextlib.contextmanager
def processes_ended(grace=10):
	"""Every process started with subprocess.Popen (subprocess.run's too) inside the block, if still running at its
	end, is ended then: terminated (SIGTERM, on which rig.py ends its job and logs RIG_ABORTED; on Windows it ends the
	process outright), and killed if it is still there grace seconds later. Yields the list of processes started."""
	started, before = [], subprocess.Popen

	class Popen(before):
		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			started.append(self)

	subprocess.Popen = Popen
	try:
		yield started
	finally:
		subprocess.Popen = before
		left = [p for p in started if p.poll() is None]
		for p in left:
			p.terminate()
		for p in left:
			try:
				p.wait(grace)
			except subprocess.TimeoutExpired:
				p.kill()
				p.wait()


@pytest.fixture(autouse=True)
def no_process_left_running():
	# A test that fails between starting a process and waiting for it (a wait that timed out, an assert) would leave
	# it running after the tests. A rig.py run left waiting (for the rig, or for the machine to be quiet) then waits
	# for ever, and every rig.py install on the machine refuses to run beside it
	with processes_ended():
		yield
