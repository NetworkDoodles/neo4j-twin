"""make status · what's installed, what's running, and where to start.

The dev container runs this when the folder opens. It only reads: package versions, and one `show version`
per switch through its console, and one query to Neo4j. Safe to run any time.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import pathlib
from importlib import metadata

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import fabric, lab  # noqa: E402

GUIDE = "https://networkdoodles.com/labs/neo4j-twin"
TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
G, R, Y, C, D, B, X = (("\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m")
                       if TTY else ("",) * 7)
SWITCHES = fabric.switches()


def sh(*cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (p.stdout + p.stderr).strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def row(ok, name, value, fix=""):
    mark = f"{G}✓{X}" if ok else (f"{Y}·{X}" if ok is None else f"{R}✗{X}")
    print(f"  {mark} {name:<14} {value if ok else (D + fix + X if fix else value)}")


def version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def switches():
    up = {}
    for sw in SWITCHES:
        if not lab.ready(sw):
            continue
        m = re.search(r"capeos\.(\S+)", lab.show(sw, "show version", timeout=10) or "")
        up[sw] = f"CapeOS {m.group(1)}" if m else "up"
    return up


print(f"\n{B}{C}  Network Doodles lab · Graph digital twins with Neo4j{X}\n")
print(f"{D}  tools{X}")
row(True, "python", sys.version.split()[0])
v = version("neo4j")
row(bool(v), "neo4j driver", v, "not installed: make setup")
v = version("fastmcp")
row(bool(v), "fastmcp", v, "not installed: make setup")
v = sh("docker", "version", "--format", "{{.Server.Version}}")
row(bool(v), "docker", v, "not answering")
m = re.search(r'"version":\s*"([^"]+)"', sh("containerlab", "version", "--json") or "") if shutil.which("containerlab") else None
row(bool(m), "containerlab", m.group(1) if m else "", "not found: it comes with the dev container")

up = switches()
if "--wait" in sys.argv and len(up) < len(SWITCHES):
    # The folder-open task can run before the dev container has started the fabric.
    print(f"\n  {Y}·{X} the fabric is starting: about a minute", flush=True)
    deadline = time.time() + 10 * 60
    while time.time() < deadline and len(up) < len(SWITCHES):
        time.sleep(10)
        up = switches()

print(f"\n{D}  switches (CapeOS Pulse){X}")
mgmt = fabric.mgmt()
for sw in SWITCHES:
    row(sw in up, sw, f"{mgmt[sw]}  {up.get(sw, '')}", "not answering: make up")
try:
    faults = json.loads((fabric.ROOT / "build" / "faults.json").read_text())
except (OSError, ValueError):
    faults = []
if faults:
    print(f"\n  {Y}·{X} broken on purpose: {', '.join(f['fault'] for f in faults)}  (make fix puts it back)")
print(f"\n{D}  the graph twin{X}")
try:
    from lib import twin
    n = twin.one("MATCH (n) RETURN count(n)")
    row(True, "neo4j", f"http://localhost:7474  {n} nodes  (user neo4j, password lab-twin-graph)")
except Exception:
    row(False, "neo4j", "", "not answering: make up starts it")
print(f"\n  Start here: {C}{GUIDE}/{X}   ·   make help lists everything\n")
