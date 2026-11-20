"""make collect · task 3.1: read the network's state from every switch, into a snapshot on disk.

    python twin/collect.py          writes build/snapshots/<time>/<switch>.json and meta.json

Each switch has a JSON-RPC command API: you POST a list of show commands to https://<switch>/command-api and get
the same commands' output back as JSON, one result per command. That's what this script asks for: LLDP
neighbors, interface status and BGP sessions, from all six switches at once.

It doesn't touch the graph. A snapshot is the raw evidence, exactly what each switch said and when, kept on disk;
task 3.2 decides what it means for the twin. Keeping the two apart means you can load an old snapshot again, or
diff two of them (task 6.1), without asking the switches anything.

The credentials are the lab switches' own, from the environment (the dev container sets them). Real ones come
from a vault.
"""
import concurrent.futures
import datetime as dt
import json
import os
import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
from lib import fabric  # noqa: E402

SNAPSHOTS = ROOT / "build" / "snapshots"
USER = os.environ.get("SWITCH_USERNAME", "admin")
PASSWORD = os.environ.get("SWITCH_PASSWORD", "capeos-lab")


def run_cmds(host, cmds):
    """Send show commands to one switch's command API; return their results, in order, as Python objects."""
    # TODO 3.1a  (follow along) The JSON-RPC request. POST this body to f"https://{host}/command-api", with basic
    #            auth (USER, PASSWORD), verify=False (the lab switches have self-signed certificates) and a
    #            10-second timeout:
    #              {"jsonrpc": "2.0", "method": "runCmds", "id": 1,
    #               "params": {"version": 1, "cmds": cmds, "format": "json"}}
    #            The reply is {"jsonrpc": "2.0", "id": 1, "result": [one dict per command]}, or "error" instead of
    #            "result" if a command failed: raise RuntimeError with the error's message then.
    # >>> solution
    body = {"jsonrpc": "2.0", "method": "runCmds", "id": 1,
            "params": {"version": 1, "cmds": cmds, "format": "json"}}
    r = httpx.post(f"https://{host}/command-api", json=body, auth=(USER, PASSWORD), verify=False, timeout=10)
    r.raise_for_status()
    reply = r.json()
    if "error" in reply:
        raise RuntimeError(reply["error"].get("message", reply["error"]))
    return reply["result"]
    # <<< solution


# What to ask every switch for, and the name each answer is kept under in the snapshot.
# TODO 3.1a  (follow along, continued) Two entries: "lldp" for "show lldp neighbors", and "interfaces" for
#            "show interfaces status".
# TODO 3.1b  (challenge) One more: "bgp", for the BGP sessions. Which show command lists them, with their state?
COMMANDS = {
    # >>> solution | # TODO 3.1a: "lldp" and "interfaces"
    "lldp": "show lldp neighbors",
    "interfaces": "show interfaces status",
    # <<< solution
    # >>> solution | # TODO 3.1b: "bgp"
    "bgp": "show ip bgp summary",
    # <<< solution
}


def collect(name, host):
    """One switch's state: {"lldp": ..., "interfaces": ..., "bgp": ...}, each its command's raw JSON."""
    return dict(zip(COMMANDS, run_cmds(host, list(COMMANDS.values()))))


def main():
    if not COMMANDS:
        sys.exit("COMMANDS is empty: TODO 3.1a is still open")
    started = time.monotonic()
    at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    out = SNAPSHOTS / at.strftime("%Y%m%dT%H%M%SZ")
    while out.exists():          # two collections in the same second: the second one waits for the next
        time.sleep(0.2)
        at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        out = SNAPSHOTS / at.strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    switches = fabric.mgmt()
    results, failed = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(switches)) as pool:
        jobs = {pool.submit(collect, n, h): n for n, h in switches.items()}
        for job in concurrent.futures.as_completed(jobs):
            name = jobs[job]
            try:
                results[name] = job.result()
            except NotImplementedError:
                raise
            except Exception as e:  # one switch not answering shouldn't lose the other five
                failed[name] = f"{type(e).__name__}: {e}"
    if not results:      # nothing to keep: don't leave an empty snapshot to be loaded as the newest
        out.rmdir()
        for name, why in sorted(failed.items()):
            print(f"  ✗ {name}: {why}")
        return 1
    for name, state in results.items():
        (out / f"{name}.json").write_text(json.dumps(state, indent=1, sort_keys=True))
    seconds = round(time.monotonic() - started, 2)
    meta = {"collected_at": at.isoformat().replace("+00:00", "Z"), "switches": sorted(results),
            "failed": failed, "seconds": seconds}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"  snapshot {out.relative_to(ROOT)}: {len(results)} of {len(switches)} switches in {seconds} s")
    for name, why in sorted(failed.items()):
        print(f"  ✗ {name}: {why}")
    return 0 if results else 1


def latest(n=1):
    """The newest n snapshot folders, newest first."""
    return sorted((p for p in SNAPSHOTS.glob("*T*Z") if (p / "meta.json").exists()), reverse=True)[:n]


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    sys.exit(main())
