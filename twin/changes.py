"""task 6.1: what changed in the network between the last two snapshots?

    python twin/changes.py                  the newest snapshot against the one before it
    python twin/changes.py <older> <newer>  any two snapshot folders

`make refresh` runs this after every collect and load. The graph only holds the network as it is now (task 3.2
removes what's gone), so the history lives where the evidence does: the snapshots on disk. Diffing two of them
answers "what changed since last time?" without asking the switches anything, and works for any two points in
time you still have a snapshot of.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, (ROOT / "twin").as_posix())
import collect  # noqa: E402


def state(snapshot):
    meta = json.loads((snapshot / "meta.json").read_text())
    return meta["collected_at"], {sw: json.loads((snapshot / f"{sw}.json").read_text()) for sw in meta["switches"]}


def lldp_changes(old, new):
    """(gone, appeared): sorted lists of "leaf1:Ethernet2 -> spine2:Ethernet1", one per LLDP neighbor."""
    # TODO 6.1a  (follow along) Turn each snapshot's LLDP into a set of strings, one per neighbor a switch reports:
    #            f"{switch}:{n['port']} -> {n['neighborDevice']}:{n['neighborPort']}" for every n in
    #            state[switch]["lldp"]["lldpNeighbors"]. Then gone is old minus new, appeared is new minus old.
    # >>> solution
    def facts(s):
        return {f"{sw}:{n['port']} -> {n['neighborDevice']}:{n['neighborPort']}"
                for sw, st in s.items() for n in st.get("lldp", {}).get("lldpNeighbors", [])}
    a, b = facts(old), facts(new)
    return sorted(a - b), sorted(b - a)
    # <<< solution


def bgp_changes(old, new):
    """Sorted list of (switch, peer, old state, new state) for every BGP session whose state changed.
    A session that's only in one snapshot has state "missing" in the other. peer is the session's description
    (the peer's name) if it has one, otherwise its address."""
    # TODO 6.1b  (challenge) Build {(switch, peer): state} for each snapshot from
    #            state[switch]["bgp"]["vrfs"][vrf]["peers"][address] (peerState, description), then compare.
    # >>> solution | return []  # TODO 6.1b (challenge): not done yet
    def facts(s):
        return {(sw, p.get("description") or ip): p["peerState"]
                for sw, st in s.items() for vrf in st.get("bgp", {}).get("vrfs", {}).values() for ip, p in vrf["peers"].items()}
    a, b = facts(old), facts(new)
    return sorted((sw, peer, a.get((sw, peer), "missing"), b.get((sw, peer), "missing"))
                  for sw, peer in set(a) | set(b) if a.get((sw, peer)) != b.get((sw, peer)))
    # <<< solution


def main(older=None, newer=None):
    if older and newer:
        pair = [pathlib.Path(newer), pathlib.Path(older)]
    else:
        pair = collect.latest(2)
        if len(pair) < 2:
            return print("  only one snapshot so far: nothing to compare yet")
    (t_new, new), (t_old, old) = state(pair[0]), state(pair[1])
    gone, appeared = lldp_changes(old, new)
    bgp = bgp_changes(old, new)
    print(f"  changes from {t_old} to {t_new}:")
    for g in gone:
        print(f"  - lldp gone      {g}")
    for a in appeared:
        print(f"  + lldp appeared  {a}")
    for sw, peer, was, now in bgp:
        print(f"  ~ bgp            {sw} -> {peer}: {was} → {now}")
    if not (gone or appeared or bgp):
        print("  = nothing changed")


if __name__ == "__main__":
    main(*sys.argv[1:3])
