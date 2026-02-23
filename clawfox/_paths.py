"""Paths and config for clawfox daemon and CLI."""
import os

_BASE = os.environ.get("CLAWFOX_HOME", os.path.expanduser("~/.clawfox"))
RUN_DIR = os.path.join(_BASE, "run")
SOCKET_PATH = os.path.join(RUN_DIR, "socket")
PIDFILE_PATH = os.path.join(RUN_DIR, "daemon.pid")
SCREENSHOT_DIR = os.path.join(_BASE, "screenshots")
DEFAULT_GO_TIMEOUT_MS = 30_000
SCREENSHOT_MAX_AGE_SECONDS = 24 * 3600  # 1 day
