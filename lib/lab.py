"""Lab plumbing shared by the checker, the status page and the fault scripts.

`cli(sw, ...)` and `show(sw, ...)` run CLI lines through the switch's own console (docker exec). The lab uses
them to break and fix things, and to wait for the fabric. Your own code reaches the switches the other way, through
their command API (twin/collect.py).
"""
import subprocess

from lib import fabric

ROOT = fabric.ROOT


def cli(sw, *lines, timeout=30):
    """Feed lines to the switch's CLI. Config lines need 'configure' first and 'end' last."""
    p = subprocess.run(["docker", "exec", "-i", sw, "capeos-cli"], input="\n".join(lines) + "\n",
                       capture_output=True, text=True, timeout=timeout)
    return p.stdout


def show(sw, command, timeout=30):
    p = subprocess.run(["docker", "exec", sw, "capeos-cli", "-c", command], capture_output=True, text=True, timeout=timeout)
    return p.stdout


def ready(sw):
    return subprocess.run(["docker", "exec", sw, "test", "-f", "/run/capeos/ready"], capture_output=True).returncode == 0


def wait_api(sw, timeout=120):
    """After the command API is turned back on, wait until it's serving again (CapeOS takes up to a minute)."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "HTTPS server: running" in show(sw, "show management api http-commands"):
            return True
        time.sleep(3)
    return False
