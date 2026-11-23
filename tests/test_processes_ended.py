"""conftest.py's no_process_left_running: what a test started and left running is ended when the test ends. A test that
fails between starting a rig.py and waiting for it (a wait that timed out, an assert) would otherwise leave that rig.py
running after the tests: a rig.py run left waiting for the rig, or for the machine to be quiet, waits for ever, and
every rig.py install on the machine refuses to run beside it.
"""

import os, signal, subprocess, sys, time

import pytest

import conftest

LOCK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # this repository: the lock files are at its top
RIG = os.path.join(LOCK_DIR, "rig.py")


def test_what_is_left_running_is_ended_and_what_ended_is_left_alone():
	with conftest.processes_ended() as started:
		left = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
		done = subprocess.run([sys.executable, "-c", "pass"])
		assert left.poll() is None
	assert len(started) == 2 and started[0] is left and done.returncode == 0
	assert left.poll() is not None  # ended at the block's end, not 120 s later


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM to ignore: terminate ends a process there")
def test_one_that_ignores_sigterm_is_killed_after_the_grace():
	stubborn = "import signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(120)"
	t = time.monotonic()
	with conftest.processes_ended(grace=1):
		p = subprocess.Popen([sys.executable, "-c", stubborn], stdout=subprocess.PIPE, text=True)
		assert p.stdout.readline().strip() == "ready"
	p.stdout.close()
	assert p.returncode == -signal.SIGKILL and time.monotonic() - t < 30


@pytest.mark.alone
def test_a_rig_py_left_waiting_for_the_rig_is_ended(tmp_path):
	# As in a test whose wait for its rig.py run timed out: the run, waiting behind a held rig, was never waited for
	root = tmp_path / "root"
	root.mkdir()
	(root / "gpu.lock").write_text("someone 2026-11-22 20:00\n")  # a lock written by hand: held until it is removed
	ran = tmp_path / "ran"
	env = dict(os.environ, RIG_ROOT=str(root), RIG_LOCK="file", RIG_PERIOD="0.3")
	for name in ("RIG_JOB", "RIG_TAG", "RIG_LOGDIR", "RIG_GPU", "RIG_WHOLE"):
		env.pop(name, None)
	with conftest.processes_ended():
		r = subprocess.Popen([sys.executable, RIG, "run", "tester", "left", "--", sys.executable, "-c",
			"open(%r, 'w').close()" % str(ran)], env=env, cwd=str(tmp_path), stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL)
		time.sleep(2)
		assert r.poll() is None  # still waiting for the rig
	assert r.poll() is not None and not ran.exists()  # ended, and its job never started
	assert (root / "gpu.lock").read_text() == "someone 2026-11-22 20:00\n"  # the holder's lock untouched
