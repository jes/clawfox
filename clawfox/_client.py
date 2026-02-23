"""Client: ensure daemon is running, send one command, return output or raise."""
from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import sys
import time

from ._paths import RUN_DIR, SOCKET_PATH, PIDFILE_PATH

STARTUP_LOCK_PATH = os.path.join(RUN_DIR, "startup.lock")


def _daemon_running() -> bool:
    if not os.path.exists(SOCKET_PATH) or not os.path.exists(PIDFILE_PATH):
        return False
    try:
        with open(PIDFILE_PATH) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(SOCKET_PATH)
        s.close()
        return True
    except (socket.error, OSError):
        return False


def ensure_daemon():
    """If daemon not running, start it and wait for socket. Uses a lock so only one process starts the daemon."""
    if _daemon_running():
        return
    os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
    with open(STARTUP_LOCK_PATH, "a") as lock_file:
        lock_file.flush()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if _daemon_running():
                return
            subprocess.Popen(
                [sys.executable, "-m", "clawfox", "daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            for _ in range(30):
                time.sleep(0.2)
                if _daemon_running():
                    return
            raise RuntimeError("clawfox daemon did not start in time")
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def send_command(cmd: str, **args) -> str:
    """Send one command; return output string. Raises on error response."""
    ensure_daemon()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(60)
    try:
        s.connect(SOCKET_PATH)
        req = json.dumps({"cmd": cmd, "args": args}) + "\n"
        s.sendall(req.encode("utf-8"))
        buf = b""
        while b"\n" not in buf and len(buf) < 10_000_000:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.decode("utf-8", errors="replace").split("\n", 1)[0]
        out = json.loads(line)
    finally:
        try:
            s.close()
        except Exception:
            pass
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "unknown error"))
    return out.get("output", "")
