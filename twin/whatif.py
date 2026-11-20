"""make whatif C=<change> · task 5.2: try a change on the graph, see what it would do, and leave no trace.

    python twin/whatif.py changes/lose-spine2-leaf1.yml

A change file lists links to remove (an interface id at either end) and devices to drain (every link of theirs
removed). The script opens one transaction, makes the change inside it, asks two questions there, and rolls the
transaction back. Inside the transaction the graph has the change; outside it, nobody ever sees it, and nothing
is written. That's a what-if: the twin's answer to "what happens if", without touching the twin.

    broken now          flows with no path left at all, with the change made
    new single points   devices that become a single point of failure for a tier 1 service because of the
                        change: queries/spof.cypher (task 5.1) run after the change, minus the same file before it
"""
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
from lib import twin  # noqa: E402

SPOF = (ROOT / "queries" / "spof.cypher").read_text()


def statement(text):
    """The one query in a .cypher file, without its comments or the trailing ;"""
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("//")).strip().rstrip(";")


def apply(tx, change):
    """Make the change inside the transaction. Returns how many CABLED_TO relationships it removed."""
    # TODO 5.2a  (follow along) Two DELETEs, each with its list as a parameter:
    #            change.get("remove_links", []): a CABLED_TO with an interface whose id is in the list at either
    #              end. MATCH (a:Interface)-[r:CABLED_TO]-(b:Interface) WHERE a.id IN $ids DELETE r
    #            change.get("drain", []): every CABLED_TO on an interface of a device in the list.
    #            Return the total number deleted: .consume().counters.relationships_deleted on each result.
    #            Delete only CABLED_TO, never a node: the change is to the cabling, and the rollback undoes it anyway.
    raise NotImplementedError("TODO 5.2a is still open")


def broken_now(tx):
    """[(service, flow)]: flows that have no path at all, as the graph stands inside this transaction."""
    # TODO 5.2b  (challenge) Task 5.1's blast radius with nothing failed: every Service -[:DEPENDS_ON]-> App
    #            -[:TALKS_TO]-> App whose two hosts have no path at all (NOT EXISTS, no none() needed).
    #            Return [(service name, "a -> b :port"), ...], sorted. Run it with tx.run, not a new session: a
    #            new session wouldn't see the change.
    raise NotImplementedError("TODO 5.2b is still open")


def spofs(tx):
    return {r["device"]: sorted(r["breaks"]) for r in tx.run(statement(SPOF))}


def main(path):
    change = yaml.safe_load(pathlib.Path(path).read_text())
    with twin.driver() as d, d.session() as s:
        tx = s.begin_transaction()
        try:
            before = spofs(tx)
            removed = apply(tx, change)
            now = broken_now(tx)
            after = spofs(tx)
        finally:
            tx.rollback()          # whatever happened above, none of it is kept
    print(f"  what if: {change.get('description', path)}  ({removed} link{'s' if removed != 1 else ''} removed, inside a transaction)")
    if now:
        for service, flow in now:
            print(f"  ✗ broken now: {service}: {flow}")
    else:
        print("  ✓ broken now: nothing, every flow still has a path")
    new = {dev: [s for s in svcs if s not in before.get(dev, [])] for dev, svcs in after.items()}
    new = {dev: svcs for dev, svcs in new.items() if svcs}
    for dev, svcs in sorted(new.items()):
        print(f"  ! new single point of failure: {dev}, for {', '.join(svcs)}")
    if not new:
        print("  ✓ no new single points of failure")
    print("  rolled back: the graph is as it was")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python twin/whatif.py changes/<change>.yml")
    main(sys.argv[1])
