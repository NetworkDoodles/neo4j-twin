"""make break X=<fault> · make fix   ·   break the fabric on purpose, then put it back.

    link   the cable between spine2 and leaf1 goes dark: spine2 shuts Ethernet1, so leaf1 loses LLDP and BGP on
           that port too (chapters 4 and 6)
    bgp    leaf2 shuts its BGP session to spine1; every interface stays up and LLDP still sees the neighbor

The faults go in through each switch's own console, not the API. `make fix` undoes everything this script did;
`make reset` rebuilds the whole fabric if all else fails.
"""
import json
import sys
import pathlib

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import fabric, lab  # noqa: E402

STATE = fabric.ROOT / "build" / "faults.json"


def faults():
    intent = fabric.load()
    leaf2_up = fabric.interfaces(intent)["leaf2"]["Ethernet1"]
    asn = fabric.asn(intent, "leaf2")
    return {
        "link": {"fault": "link", "device": "spine2", "interface": "Ethernet1",
                 "do": ["spine2", "interface Ethernet1", "shutdown"],
                 "undo": ["spine2", "interface Ethernet1", "no shutdown"]},
        "bgp": {"fault": "bgp", "device": "leaf2", "interface": "Ethernet1",
                "do": ["leaf2", f"router bgp {asn}", f"neighbor {leaf2_up['peer_ip']} shutdown"],
                "undo": ["leaf2", f"router bgp {asn}", f"no neighbor {leaf2_up['peer_ip']} shutdown"]},
    }


def config(sw, *lines):
    lab.cli(sw, "configure", *lines, "end")


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return []


def apply(f):
    sw, *lines = f["do"]
    config(sw, *lines)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(load_state() + [f], indent=1))


def fix():
    done = load_state()
    for f in reversed(done):
        sw, *lines = f["undo"]
        config(sw, *lines)
    STATE.unlink(missing_ok=True)
    if done:
        print(f"  put back: {', '.join(f['fault'] + ' on ' + f['device'] for f in done)}. BGP and LLDP need a few seconds.")
    else:
        print("  nothing to fix")


def main(kind):
    if kind == "fix":
        return fix()
    if kind == "forget":          # make up: a fresh fabric has no faults
        STATE.unlink(missing_ok=True)
        return
    f = faults().get(kind)
    if not f:
        raise SystemExit(f"no fault called {kind}: try link or bgp")
    if any(x["fault"] == kind for x in load_state()):
        return print(f"  {kind} is already broken. `make fix` puts it back.")
    apply(f)
    print(f"  broke it: {kind} ({f['device']} {f['interface']}). `make fix` puts it back.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
