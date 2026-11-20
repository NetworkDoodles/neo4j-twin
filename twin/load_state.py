"""task 3.2: load a snapshot from task 3.1 into the graph, as observed state next to the intent.

    python twin/load_state.py                       the newest snapshot in build/snapshots/
    python twin/load_state.py build/snapshots/<t>   a particular one

The intent says spine1:Ethernet1 is CABLED_TO leaf1:Ethernet1. The snapshot says what leaf1 actually sees on
that port. Both go in the same graph, as different relationship types, so one query can compare them (chapter 4):

    (Interface)-[:LLDP_NEIGHBOR {seen_at}]->(Interface)      what a switch's LLDP reports on a port
    (Device)-[:BGP_PEER {state, prefixes, seen_at, last_seen}]->(Device)
    Interface.oper_status, Interface.observed_at, Device.observed_at

Each relationship points from the switch that reported it, so a healthy link has two LLDP_NEIGHBORs, one each
way. seen_at is the collection that last reported it. A fact the newest snapshot doesn't report any more is
deleted at the end of the load, so the graph never claims a neighbor that has gone (chapter 6 keeps a record
of what went).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
from lib import twin  # noqa: E402
sys.path.insert(0, (ROOT / "twin").as_posix())
import collect  # noqa: E402


def read(snapshot):
    """{"at": "2026-...Z", "switches": [...], "state": {switch: {"lldp": ..., "interfaces": ..., "bgp": ...}}}"""
    meta = json.loads((snapshot / "meta.json").read_text())
    state = {sw: json.loads((snapshot / f"{sw}.json").read_text()) for sw in meta["switches"]}
    return {"at": meta["collected_at"], "switches": meta["switches"], "state": state}


def rows(snap):
    """The switches' raw JSON, flattened into rows for the queries below."""
    interfaces, lldp, bgp = [], [], []
    for sw, s in snap["state"].items():
        for port, i in s.get("interfaces", {}).get("interfaceStatuses", {}).items():
            interfaces.append({"id": f"{sw}:{port}", "status": i["lineProtocolStatus"]})
        for n in s.get("lldp", {}).get("lldpNeighbors", []):
            lldp.append({"from": f"{sw}:{n['port']}", "to": f"{n['neighborDevice']}:{n['neighborPort']}"})
        for vrf in s.get("bgp", {}).get("vrfs", {}).values():
            for ip, p in vrf["peers"].items():
                bgp.append({"device": sw, "peer_ip": ip, "state": p["peerState"], "prefixes": p.get("prefixAccepted", 0)})
    return {"interfaces": interfaces, "lldp": lldp, "bgp": bgp}


def load_lldp(tx, data, at):
    """Interface status, and what LLDP sees on each port."""
    # TODO 3.2a  (follow along) Two UNWINDs.
    #            data["interfaces"] ({id, status}): MATCH the Interface by id and SET oper_status = status and
    #            observed_at = $at. A port the intent doesn't have (Management0) has no node, so MATCH skips it.
    #            data["lldp"] ({from, to}, two interface ids): MATCH both interfaces, MERGE
    #            (from)-[r:LLDP_NEIGHBOR]->(to), and SET r.seen_at = $at.
    # >>> solution
    tx.run("""
        UNWIND $rows AS row
        MATCH (i:Interface {id: row.id})
        SET i.oper_status = row.status, i.observed_at = $at
    """, rows=data["interfaces"], at=at)
    tx.run("""
        UNWIND $rows AS row
        MATCH (a:Interface {id: row.from}), (b:Interface {id: row.to})
        MERGE (a)-[r:LLDP_NEIGHBOR]->(b)
        SET r.seen_at = $at
    """, rows=data["lldp"], at=at)
    # <<< solution


def load_bgp(tx, data, at):
    """BGP sessions, device to device."""
    # TODO 3.2b  (challenge) data["bgp"] ({device, peer_ip, state, prefixes}). A switch names its BGP peer by IP
    #            address, not by name, so find the peer the way the network does: the Device with an Interface
    #            whose ip (stored as "10.0.11.0/31") has that address. split(i.ip, "/")[0] is the address alone.
    #            MERGE (device)-[r:BGP_PEER]->(peer) and SET state, prefixes and seen_at = $at. last_seen is the last
    #            time the session was Established: $at if it is now, otherwise leave it as it was
    #            (CASE WHEN ... THEN $at ELSE r.last_seen END).
    # >>> solution | pass  # TODO 3.2b (challenge): not done yet
    tx.run("""
        UNWIND $rows AS row
        MATCH (d:Device {name: row.device})
        MATCH (p:Device)-[:HAS_INTERFACE]->(i:Interface)
        WHERE split(i.ip, "/")[0] = row.peer_ip
        MERGE (d)-[r:BGP_PEER]->(p)
        SET r.state = row.state, r.prefixes = row.prefixes, r.seen_at = $at,
            r.last_seen = CASE WHEN row.state = "Established" THEN $at ELSE r.last_seen END
    """, rows=data["bgp"], at=at)
    # <<< solution


def prune(tx, switches, at):
    """Delete what the switches in this snapshot reported before but not this time. Returns what went."""
    gone = tx.run("""
        MATCH (d:Device)-[:HAS_INTERFACE]->(a:Interface)-[r:LLDP_NEIGHBOR]->(b:Interface)
        WHERE d.name IN $switches AND r.seen_at <> $at
        WITH a, b, r, "lldp " + a.id + " -> " + b.id AS what
        DELETE r
        RETURN what
    """, switches=switches, at=at).value()
    gone += tx.run("""
        MATCH (d:Device)-[r:BGP_PEER]->(p:Device)
        WHERE d.name IN $switches AND r.seen_at <> $at
        WITH r, "bgp " + d.name + " -> " + p.name AS what
        DELETE r
        RETURN what
    """, switches=switches, at=at).value()
    tx.run("MATCH (d:Device) WHERE d.name IN $switches SET d.observed_at = $at", switches=switches, at=at)
    return gone


def main(path=None):
    snapshot = pathlib.Path(path) if path else next(iter(collect.latest()), None)
    if not snapshot:
        sys.exit("no snapshot yet: make collect (task 3.1) writes one")
    snap = read(snapshot)
    data = rows(snap)
    at = snap["at"]
    with twin.driver() as d, d.session() as s:
        gone = s.execute_write(lambda tx: (load_lldp(tx, data, at), load_bgp(tx, data, at),
                                           prune(tx, snap["switches"], at))[-1])
    c = twin.counts()
    up = twin.one("MATCH ()-[r:BGP_PEER {state: 'Established'}]->() RETURN count(r)")
    print(f"  loaded {snapshot.relative_to(ROOT) if snapshot.is_relative_to(ROOT) else snapshot} ({at}): "
          f"{c.get('LLDP_NEIGHBOR', 0)} LLDP_NEIGHBOR, {c.get('BGP_PEER', 0)} BGP_PEER ({up} Established)")
    for g in gone:
        print(f"  - not reported any more: {g}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
