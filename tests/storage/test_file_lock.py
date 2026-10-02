"""The actual file lock excludes a second process and releases on errors."""
from __future__ import annotations

import subprocess
import sys

from dinarledger.storage.json_store import _FileLock


def test_lock_excludes_another_process_and_releases(tmp_path):
    path = tmp_path / "items.json"
    lock_path = path.with_suffix(".json.lock")
    probe = """
import os, sys
fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR)
try:
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(3)
finally:
    os.close(fd)
"""
    try:
        with _FileLock(path):
            result = subprocess.run([sys.executable, "-c", probe, str(lock_path)])
            assert result.returncode == 3
            raise RuntimeError("abort")
    except RuntimeError:
        pass
    result = subprocess.run([sys.executable, "-c", probe, str(lock_path)])
    assert result.returncode == 0
