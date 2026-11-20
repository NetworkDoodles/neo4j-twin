"""Wait until every switch has booted, answers on its command API and has its BGP sessions up."""
import sys
import time
import pathlib

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import fabric, lab  # noqa: E402

PEERS = {n: len(p) for n, p in fabric.interfaces().items()}


def established(sw):
    return lab.show(sw, "show ip bgp summary").count("Estab")


deadline = time.time() + 240
pending = list(PEERS)
while pending:
    pending = [sw for sw in pending if not (lab.ready(sw) and established(sw) >= PEERS[sw])]
    if pending:
        if time.time() > deadline:
            sys.exit(f"these didn't come up in 4 minutes: {', '.join(pending)}   (docker logs <name> says why)")
        print(f"  waiting for {', '.join(pending)} ...", flush=True)
        time.sleep(5)
print("  the fabric is up: six switches, every BGP session established", flush=True)
from lib import twin  # noqa: E402
twin.wait()
print("\n  Neo4j is up too: http://localhost:7474 (neo4j / lab-twin-graph). Start with task 1.1\n")
