"""make check T=2.1 · CH=2 · (nothing)  ·  verifies a task, a chapter or the whole lab.

Every check runs the real thing: your .cypher files against Neo4j, your loaders against the switches' own state,
your MCP server through an MCP client. Where a task claims a query catches something, the checker breaks the
fabric on purpose, collects again, checks that your query sees it, and puts the fabric back.

    python checks/check.py 2.1          one task
    python checks/check.py ch2          one chapter
    python checks/check.py all          everything
    python checks/check.py --files 2.1  the files task 2.1 asks you to edit (make solve uses this)

Chapter 1's file starts by emptying the graph. When the graph already had chapter 2's model in it, checking
chapter 1 loads it again afterwards (the schema, the intent, and the newest snapshot).
"""
import asyncio
import importlib.util
import json
import logging
import os
import re
import pathlib
import subprocess
import sys
import tempfile
import time

import yaml

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import fabric, lab, twin  # noqa: E402

ROOT = fabric.ROOT
GUIDE = "https://networkdoodles.com/labs/neo4j-twin"
TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
C = {k: (v if TTY else "") for k, v in dict(g="\033[32m", r="\033[31m", y="\033[33m", c="\033[36m", d="\033[2m", b="\033[1m", x="\033[0m").items()}
INTENT = fabric.load()
SERVICES = yaml.safe_load((ROOT / "fabric" / "services.yml").read_text())
SNAPSHOTS = ROOT / "build" / "snapshots"


# ── helpers ────────────────────────────────────────────────────────────────────
class Unfinished(Exception):
    pass


def statements(path):
    p = ROOT / path
    if not p.exists():
        raise Unfinished(f"{path} isn't there")
    lines = [l for l in p.read_text().splitlines() if not l.strip().startswith("//")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def query(path, **params):
    """Run a .cypher file; return the rows of its last statement that returns any columns."""
    stmts = statements(path)
    if not stmts:
        raise Unfinished(f"{path} has no query in it yet")
    out = []
    with twin.driver() as d:
        for s in stmts:
            records, _, keys = d.execute_query(s, params)
            if keys:
                out = [r.data() for r in records]
    return out


def query_in(tx, path, **params):
    stmts = statements(path)
    if not stmts:
        raise Unfinished(f"{path} has no query in it yet")
    return [r.data() for r in tx.run(stmts[-1], params)]


def py(path, *args, timeout=300):
    p = subprocess.run([sys.executable, str(ROOT / path), *args], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "NO_COLOR": "1"}, timeout=timeout)
    out = p.stdout + p.stderr
    if "NotImplementedError" in out:
        todo = next((l.split("NotImplementedError: ")[-1] for l in out.splitlines() if "NotImplementedError: " in l), "a TODO is still open")
        raise Unfinished(f"{path}: {todo}")
    return p.returncode, out


def module(path):
    spec = importlib.util.spec_from_file_location(pathlib.Path(path).stem + "_under_test", ROOT / path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((ROOT / path).parent))
    spec.loader.exec_module(m)
    return m


def snapshots():
    return sorted(p for p in SNAPSHOTS.glob("*T*Z") if (p / "meta.json").exists())


def schema_ready():
    return twin.one("MATCH (i:Interface) RETURN count(i)") or 0


def rebuild():
    """Put chapter 2 and 3's graph back: the schema, the intent, the newest snapshot."""
    subprocess.run([sys.executable, "lab/cypher.py", "graph/schema.cypher"], cwd=ROOT, capture_output=True)
    subprocess.run([sys.executable, "twin/load_intent.py"], cwd=ROOT, capture_output=True)
    if snapshots():
        subprocess.run([sys.executable, "twin/load_state.py"], cwd=ROOT, capture_output=True)


def refresh_until(pred, timeout=60):
    """Collect and load until pred() is true (BGP and LLDP take a few seconds to notice). Returns pred()."""
    deadline = time.time() + timeout
    while True:
        py("twin/collect.py")
        py("twin/load_state.py")
        if pred() or time.time() > deadline:
            return pred()
        time.sleep(3)


def healthy():
    c = twin.counts()
    up = twin.one("MATCH ()-[r:BGP_PEER {state: 'Established'}]->() RETURN count(r)") or 0
    return c.get("LLDP_NEIGHBOR") == 16 and up == 16


class Fault:
    """Break something with lab/faults.py for the length of a with block, then put it back and wait for the
    fabric to be healthy again in the graph."""

    def __init__(self, kind):
        self.kind = kind

    def __enter__(self):
        py("lab/faults.py", self.kind)

    def __exit__(self, *exc):
        py("lab/faults.py", "fix")
        try:
            refresh_until(healthy, timeout=90)
        except Unfinished:
            pass


def faults_active():
    try:
        return bool(json.loads((ROOT / "build" / "faults.json").read_text()))
    except (OSError, ValueError):
        return False


def intent_links():
    return {(l["a"], l["b"]) for l in INTENT["links"]}


# ── chapter 1 · a network is a graph ───────────────────────────────────────────
def chapter1(fn):
    def wrapped():
        had = schema_ready()
        try:
            yield from fn()
        finally:
            if had:
                rebuild()
    wrapped.__name__ = fn.__name__
    return wrapped


@chapter1
def t1_1():
    code, out = py("lab/cypher.py", "cypher/fabric.cypher")
    if code:
        yield False, f"cypher/fabric.cypher runs ({out.strip().splitlines()[-1] if out.strip() else 'it failed'})"
        return
    devs = {r["name"]: r for r in twin.rows("MATCH (d:Device) RETURN d.name AS name, d.role AS role, d.asn AS asn")}
    links = {(r["a"], r["b"]) for r in twin.rows("MATCH (a:Device)-[:LINK]->(b:Device) RETURN a.name AS a, b.name AS b")}
    undirected = {frozenset(l) for l in links}
    want = lambda n: n in devs and devs[n]["role"] == INTENT["devices"][n]["role"] and devs[n]["asn"] == fabric.asn(INTENT, n)  # noqa: E731
    yield all(want(n) for n in ("spine1", "spine2", "leaf1")) and \
        {frozenset({"leaf1", "spine1"}), frozenset({"leaf1", "spine2"})} <= undirected, \
        "spine2 and leaf1 are Devices with their role and asn, and leaf1 has a LINK to each spine (follow along)"
    leaves = ("leaf2", "leaf3", "leaf4")
    yield all(want(n) for n in leaves) and all(frozenset({l, s}) in undirected for l in leaves for s in ("spine1", "spine2")), \
        "leaf2, leaf3 and leaf4 are there too, each with a LINK to both spines (challenge)"
    yield len(devs) == 6 and len(links) == 8 and len(undirected) == 8, \
        f"and nothing else: 6 Devices and 8 LINKs (the graph has {len(devs)} and {len(links)})"


@chapter1
def t1_2():
    if not twin.one("MATCH ()-[l:LINK]->() RETURN count(l)"):
        py("lab/cypher.py", "cypher/fabric.cypher")
    got = [r.get("neighbor") for r in query("queries/neighbors.cypher", device="leaf1")]
    yield got == ["spine1", "spine2"], f"queries/neighbors.cypher says leaf1's neighbors are spine1 and spine2 (follow along; got {got})"
    got = [r.get("neighbor") for r in query("queries/neighbors.cypher", device="spine2")]
    yield got == ["leaf1", "leaf2", "leaf3", "leaf4"], "and spine2's are the four leaves, in order: the link's direction doesn't matter"
    rows = [(r.get("device"), r.get("role"), r.get("links")) for r in query("queries/links-per-device.cypher")]
    want = [("spine1", "spine", 4), ("spine2", "spine", 4)] + [(f"leaf{i}", "leaf", 2) for i in range(1, 5)]
    yield rows == want, "queries/links-per-device.cypher: every device, its role and its link count, most links first (challenge)"


# ── chapter 2 · model the network ──────────────────────────────────────────────
def constraint_on(label, prop):
    return any(r["labelsOrTypes"] == [label] and r["properties"] == [prop] and r["type"] == "UNIQUENESS"
               for r in twin.rows("SHOW CONSTRAINTS YIELD labelsOrTypes, properties, type"))


def t2_1():
    code, out = py("lab/cypher.py", "graph/schema.cypher")
    yield code == 0 and statements("graph/schema.cypher"), "graph/schema.cypher runs"
    code2, out2 = py("lab/cypher.py", "graph/schema.cypher")
    yield code2 == 0, "and runs again without an error (IF NOT EXISTS)"
    idx = twin.rows("SHOW INDEXES YIELD labelsOrTypes, properties, type, owningConstraint "
                    "WHERE owningConstraint IS NULL AND type = 'RANGE' RETURN labelsOrTypes, properties")
    yield constraint_on("Device", "name") and constraint_on("Interface", "id") and \
        any(r["labelsOrTypes"] == ["Interface"] and r["properties"] == ["device"] for r in idx), \
        "Device.name and Interface.id are unique, and Interface.device has an index (follow along)"
    yield all(constraint_on(l, p) for l, p in (("Site", "name"), ("Subnet", "prefix"), ("Host", "name"),
                                               ("App", "name"), ("Service", "name"))), \
        "Site.name, Subnet.prefix, Host.name, App.name and Service.name are unique (challenge)"
    from neo4j.exceptions import ConstraintError
    refused = False
    with twin.driver() as d, d.session() as s:
        tx = s.begin_transaction()
        try:
            tx.run("CREATE (:Device {name: 'check-duplicate'}), (:Device {name: 'check-duplicate'})").consume()
        except ConstraintError:
            refused = True
        finally:
            if tx.closed() is False:
                tx.rollback()
    yield refused, "and Neo4j refuses a second Device with the same name"


def load():
    py("lab/cypher.py", "graph/schema.cypher")
    return py("twin/load_intent.py")


def t2_2():
    code, out = load()
    if code:
        yield False, f"twin/load_intent.py runs ({out.strip().splitlines()[-1] if out.strip() else 'it failed'})"
        return
    c = twin.counts()
    cabled = {(r["a"], r["b"]) for r in twin.rows("MATCH (a:Interface)-[:CABLED_TO]->(b:Interface) RETURN a.id AS a, b.id AS b")}
    ip_ok = twin.one("MATCH (i:Interface {id: 'leaf1:Ethernet1'})-[:IN_SUBNET]->(s:Subnet) "
                     "RETURN i.ip = '10.0.11.1/31' AND i.device = 'leaf1' AND i.name = 'Ethernet1' AND s.prefix = '10.0.11.0/31'")
    yield c.get("Interface") == 20 and c.get("HAS_INTERFACE") == 20 and c.get("Subnet") == 12 and \
        c.get("IN_SUBNET") == 20 and cabled == intent_links() and ip_ok, \
        "20 Interfaces on their devices and in their subnets, and the 8 CABLED_TOs the intent has, a to b (follow along)"
    flows = {(r["a"], r["b"], r["port"], r["proto"]) for r in twin.rows(
        "MATCH (a:App)-[t:TALKS_TO]->(b:App) RETURN a.name AS a, b.name AS b, t.port AS port, t.proto AS proto")}
    want_flows = {(f["from"], f["to"], f["port"], f["proto"]) for f in SERVICES["flows"]}
    placed = {(r["a"], r["h"], r["leaf"]) for r in twin.rows(
        "MATCH (a:App)-[:RUNS_ON]->(h:Host)-[:ATTACHED_TO]->(:Interface)<-[:HAS_INTERFACE]-(d:Device) "
        "RETURN a.name AS a, h.name AS h, d.name AS leaf")}
    want_placed = {(a, s["host"], next(n for n, d in INTENT["devices"].items() for h in d.get("hosts", []) if h["host"] == s["host"]))
                   for a, s in SERVICES["apps"].items()}
    deps = twin.one("MATCH (s:Service {name: 'Online orders', tier: 1, owner: 'ecommerce'})-[:DEPENDS_ON]->(a:App) RETURN count(a)")
    yield c.get("Host") == 4 and placed == want_placed and flows == want_flows and deps == 3 and c.get("DEPENDS_ON") == 4, \
        "hosts on their leaf ports, apps on their hosts, the 3 flows with port and proto, 2 services and what they need (challenge)"
    before = twin.fingerprint()
    load()
    yield twin.fingerprint() == before, "loading twice gives exactly the same graph"
    with tempfile.TemporaryDirectory() as d:
        moved = yaml.safe_load((ROOT / "fabric" / "services.yml").read_text())
        moved["services"]["network-monitoring"]["tier"] = 2
        p = pathlib.Path(d, "services.yml")
        p.write_text(yaml.safe_dump(moved))
        py("twin/load_intent.py", str(fabric.INTENT), str(p))
        tier = twin.rows("MATCH (s:Service {name: 'Network monitoring'}) RETURN s.tier AS t")
    load()
    yield [r["t"] for r in tier] == [2], "and a changed value is updated in place, not added as a second node"


# ── chapter 3 · load the running network ──────────────────────────────────────
def t3_1():
    before = set(snapshots())
    code, out = py("twin/collect.py")
    new = [s for s in snapshots() if s not in before]
    if code or not new:
        yield False, f"twin/collect.py writes a new snapshot ({out.strip().splitlines()[-1] if out.strip() else 'none written'})"
        return
    snap = new[-1]
    meta = json.loads((snap / "meta.json").read_text())
    state = {sw: json.loads((snap / f"{sw}.json").read_text()) for sw in meta["switches"]}
    yield sorted(state) == sorted(fabric.switches()), f"{snap.relative_to(ROOT)} has all six switches"
    lldp_ok = all(len(s.get("lldp", {}).get("lldpNeighbors", [])) == len(fabric.interfaces(INTENT)[sw]) for sw, s in state.items())
    ifs_ok = all("Ethernet1" in s.get("interfaces", {}).get("interfaceStatuses", {}) for s in state.values())
    yield lldp_ok and ifs_ok, "each one's LLDP neighbors and interface status, as the switch returned them (follow along)"
    bgp_ok = all(len(s.get("bgp", {}).get("vrfs", {}).get("default", {}).get("peers", {})) == len(fabric.interfaces(INTENT)[sw])
                 for sw, s in state.items())
    yield bgp_ok, "and its BGP sessions (challenge)"


def t3_2():
    if not schema_ready():
        load()
    if not snapshots():
        py("twin/collect.py")
    code, out = py("twin/load_state.py")
    if code:
        yield False, f"twin/load_state.py runs ({out.strip().splitlines()[-1] if out.strip() else 'it failed'})"
        return
    lldp = {(r["a"], r["b"]) for r in twin.rows("MATCH (a:Interface)-[:LLDP_NEIGHBOR]->(b:Interface) RETURN a.id AS a, b.id AS b")}
    want = intent_links() | {(b, a) for a, b in intent_links()}
    up = twin.one("MATCH (i:Interface) WHERE i.oper_status = 'up' AND i.observed_at IS NOT NULL RETURN count(i)")
    yield lldp == want and up == 20, \
        f"16 LLDP_NEIGHBORs, one each way on every cable, and all 20 interfaces up (follow along; {len(lldp)} and {up})"
    bgp = twin.rows("MATCH (a:Device)-[r:BGP_PEER]->(b:Device) RETURN a.name AS a, b.name AS b, r.state AS s, "
                    "r.prefixes AS p, r.seen_at = r.last_seen AS fresh")
    pairs = {(r["a"], r["b"]) for r in bgp}
    devpairs = {(a.split(":")[0], b.split(":")[0]) for a, b in want}
    yield pairs == devpairs and all(r["s"] == "Established" and r["fresh"] and r["p"] for r in bgp), \
        "16 BGP_PEERs between the right devices, Established, with prefixes and last_seen (challenge)"
    before = twin.fingerprint()
    py("twin/load_state.py")
    yield twin.fingerprint() == before, "loading the same snapshot again changes nothing"


# ── chapter 4 · cypher for network questions ───────────────────────────────────
def ready_graph():
    if not schema_ready():
        load()
    if faults_active():
        py("lab/faults.py", "fix")
    refresh_until(healthy, timeout=60)


def t4_1():
    if not schema_ready():
        load()
    hops = [r.get("hops") for r in query("queries/path.cypher", **{"from": "host1", "to": "host2"})]
    yield len(hops) == 1 and hops[0] and hops[0][0] == "leaf1" and hops[0][-1] == "leaf4" and len(hops[0]) == 3 and \
        hops[0][1] in ("spine1", "spine2"), f"queries/path.cypher: host1 to host2 is leaf1, a spine, leaf4 (follow along; got {hops})"
    hops = [r.get("hops") for r in query("queries/path.cypher", **{"from": "host3", "to": "host4"})]
    yield len(hops) == 1 and hops[0] and hops[0][0] == "leaf2" and hops[0][-1] == "leaf3", "and host3 to host4 is leaf2, a spine, leaf3"
    rows = query("queries/ecmp.cypher", **{"from": "host1", "to": "host2"})
    yield [(r.get("paths"), r.get("via")) for r in rows] == [(2, ["spine1", "spine2"])], \
        f"queries/ecmp.cypher: 2 equal-cost paths, via spine1 and spine2 (challenge; got {rows})"
    with twin.driver() as d, d.session() as s:
        tx = s.begin_transaction()
        try:
            tx.run("MATCH (:Interface {id: 'spine2:Ethernet4'})-[r:CABLED_TO]-() DELETE r").consume()
            rows = query_in(tx, "queries/ecmp.cypher", **{"from": "host1", "to": "host2"})
        finally:
            tx.rollback()
    yield [(r.get("paths"), r.get("via")) for r in rows] == [(1, ["spine1"])], "and only 1, via spine1, without the spine2-leaf4 cable"


def t4_2():
    ready_graph()
    links, bgp = query("queries/drift-links.cypher"), query("queries/drift-bgp.cypher")
    yield links == [] and bgp == [], f"on the healthy fabric both drift queries return nothing ({len(links)} and {len(bgp)} rows)"
    with Fault("link"):
        refresh_until(lambda: (twin.counts().get("LLDP_NEIGHBOR") or 0) < 16)
        refresh_until(lambda: (twin.one("MATCH ()-[r:BGP_PEER]->() WHERE r.state <> 'Established' RETURN count(r)") or 0) >= 2, 30)
        links = query("queries/drift-links.cypher")
        bgp = query("queries/drift-bgp.cypher")
    yield [(r.get("cabled"), r.get("to"), r.get("a_status"), r.get("b_status")) for r in links] == \
        [("spine2:Ethernet1", "leaf1:Ethernet2", "down", "down")], \
        f"with the spine2-leaf1 cable dark, drift-links.cypher reports that cable and both ends down (follow along; got {links})"
    yield sorted((r.get("device"), r.get("peer"), r.get("state")) for r in bgp) == [("leaf1", "spine2", "Active"), ("spine2", "leaf1", "Active")] and \
        all(r.get("last_up") for r in bgp), "and drift-bgp.cypher reports both sides of that session, Active, with when it was last up (challenge)"
    with Fault("bgp"):
        refresh_until(lambda: (twin.one("MATCH (:Device {name: 'leaf2'})-[r:BGP_PEER]->(:Device {name: 'spine1'}) RETURN r.state") or "Established") != "Established")
        links = query("queries/drift-links.cypher")
        bgp = query("queries/drift-bgp.cypher")
    yield links == [] and ("leaf2", "spine1") in {(r.get("device"), r.get("peer")) for r in bgp}, \
        "and with only leaf2's BGP session shut, the cabling is fine and drift-bgp.cypher finds the session"


# ── chapter 5 · blast radius and what-if ───────────────────────────────────────
def t5_1():
    if not schema_ready():
        load()
    got = lambda dev: [(r.get("service"), r.get("tier"), r.get("flow")) for r in query("queries/blast-radius.cypher", device=dev)]  # noqa: E731
    leaf1 = got("leaf1")
    yield leaf1 == [("Online orders", 1, "web-shop -> orders-db :5432")], f"queries/blast-radius.cypher: leaf1 takes out web-shop -> orders-db, for Online orders (follow along; got {leaf1})"
    yield got("spine1") == [] and len(got("leaf4")) == 3, "spine1 takes out nothing; leaf4 takes out three flows, for both services"
    rows = {r.get("device"): r.get("breaks") for r in query("queries/spof.cypher")}
    yield rows == {"leaf1": ["Online orders"], "leaf3": ["Online orders"], "leaf4": ["Online orders"]}, \
        f"queries/spof.cypher: leaf1, leaf3 and leaf4 are single points of failure for Online orders, and nothing else (challenge; got {rows})"
    with twin.driver() as d, d.session() as s:
        tx = s.begin_transaction()
        try:
            tx.run("MATCH (:Interface {id: 'spine2:Ethernet1'})-[r:CABLED_TO]-() DELETE r").consume()
            rows = {r.get("device"): r.get("breaks") for r in query_in(tx, "queries/spof.cypher")}
        finally:
            tx.rollback()
    yield "spine1" in rows, "and without the spine2-leaf1 cable, spine1 becomes one"


def t5_2():
    if not schema_ready():
        load()
    before = twin.fingerprint()
    code, out = py("twin/whatif.py", "changes/lose-spine2-leaf1.yml")
    yield code == 0 and "1 link removed" in out and "new single point of failure: spine1, for Online orders" in out, \
        "losing the spine2-leaf1 link removes 1 link and makes spine1 a single point of failure for Online orders (follow along)"
    code, out = py("twin/whatif.py", "changes/drain-spine1.yml")
    yield code == 0 and "4 links removed" in out and "broken now: nothing" in out, "draining spine1 removes its 4 links and breaks nothing"
    code, out = py("twin/whatif.py", "changes/maintenance-overlap.yml")
    yield code == 0 and "broken now: Online orders: web-shop -> orders-db :5432" in out, \
        "doing both at once breaks web-shop -> orders-db (challenge)"
    yield twin.fingerprint() == before, "and after all three, the graph is exactly as it was"


# ── chapter 6 · keep it current, let agents ask ────────────────────────────────
def t6_1():
    ready_graph()
    code, out = py("twin/changes.py")
    yield code == 0 and "nothing changed" in out, "twin/changes.py on two healthy snapshots: nothing changed"
    healthy_snap = snapshots()[-1]
    with Fault("link"):
        refresh_until(lambda: (twin.one("MATCH ()-[r:BGP_PEER]->() WHERE r.state <> 'Established' RETURN count(r)") or 0) >= 2)
        broken_snap = snapshots()[-1]
        code, out = py("twin/changes.py", str(healthy_snap), str(broken_snap))
    ch = module("twin/changes.py")
    _, old = ch.state(healthy_snap)
    _, new = ch.state(broken_snap)
    g, a = ch.lldp_changes(old, new)
    yield g == ["leaf1:Ethernet2 -> spine2:Ethernet1", "spine2:Ethernet1 -> leaf1:Ethernet2"] and a == [] and "lldp gone" in out, \
        f"across the fault, both ends of the spine2-leaf1 cable's LLDP are gone (follow along; got {g}, {a})"
    b = ch.bgp_changes(old, new)
    yield sorted(x[:3] for x in b) == [("leaf1", "spine2", "Established"), ("spine2", "leaf1", "Established")] and \
        all(x[3] != "Established" for x in b), f"and both sides of the session left Established (challenge; got {b})"
    g2, a2 = ch.lldp_changes(new, old)
    yield g2 == [] and len(a2) == 2 and len(ch.bgp_changes(new, old)) == 2, "and the other way round, the same facts come back"


def t6_2():
    if not schema_ready():
        load()
    ask = module("lab/ask.py")
    try:
        out = asyncio.run(ask.ask([
            ("blast_radius", {"device": "leaf1"}),
            ("path", {"src": "host1", "dst": "host2"}),
            ("cypher", {"query": "MATCH (d:Device) RETURN d.name AS name ORDER BY name"}),
            ("cypher", {"query": "MATCH (d:Device {name: $n}) SET d.role = 'changed' RETURN d.name", "params": {"n": "spine1"}}),
            ("cypher", {"query": "UNWIND range(1, 1000) AS x RETURN x"}),
        ]))
    except NotImplementedError as e:
        raise Unfinished(f"twin/mcp_server.py: {e}")
    tools = out[0][1]
    res = {i: o for i, o in enumerate(out[1:])}
    yield {"blast_radius", "path"} <= set(tools) and res[0][2] == "ok" and \
        res[0][3] == [{"service": "Online orders", "tier": 1, "flow": "web-shop -> orders-db :5432"}] and \
        res[1][2] == "ok" and res[1][3] and res[1][3][0]["hops"][0] == "leaf1", \
        "blast_radius and path answer through MCP, in a read transaction (follow along)"
    if "TODO 6.2a" in json.dumps(res[0]):
        return
    yield "cypher" in tools and res[2][2] == "ok" and [r["name"] for r in res[2][3]] == sorted(fabric.switches()), \
        "the cypher tool runs the agent's own query (challenge)"
    role = twin.one("MATCH (d:Device {name: 'spine1'}) RETURN d.role")
    yield res[3][2] == "error" and "read access mode" in res[3][3] and role == "spine", \
        "a write through it is refused by Neo4j, and spine1 is unchanged"
    yield res[4][2] == "ok" and len(res[4][3]) == 100, "and it returns at most 100 rows"


TASKS = {
    "1.1": ("the fabric by hand", ["cypher/fabric.cypher"]),
    "1.2": ("first questions", ["queries/neighbors.cypher", "queries/links-per-device.cypher"]),
    "2.1": ("the schema", ["graph/schema.cypher"]),
    "2.2": ("an idempotent load", ["twin/load_intent.py"]),
    "3.1": ("collect a snapshot", ["twin/collect.py"]),
    "3.2": ("observed state", ["twin/load_state.py"]),
    "4.1": ("paths and ECMP", ["queries/path.cypher", "queries/ecmp.cypher"]),
    "4.2": ("drift", ["queries/drift-links.cypher", "queries/drift-bgp.cypher"]),
    "5.1": ("blast radius", ["queries/blast-radius.cypher", "queries/spof.cypher"]),
    "5.2": ("what-if", ["twin/whatif.py"]),
    "6.1": ("what changed", ["twin/changes.py"]),
    "6.2": ("an MCP server", ["twin/mcp_server.py"]),
}
CHAPTERS = {1: "a network is a graph", 2: "model the network", 3: "load the running network",
            4: "cypher for network questions", 5: "blast radius and what-if", 6: "keep it current, let agents ask"}


def report(t):
    print(f"{C['c']}╭─{C['x']} {C['b']}task {t}{C['x']} {C['d']}·{C['x']} {TASKS[t][0]}", flush=True)
    results = []
    try:
        for ok, msg in globals()[f"t{t.replace('.', '_')}"]():
            ok = bool(ok)
            results.append(ok)
            if ok:   # what the checker got is only worth showing when it's wrong
                msg = re.sub(r"; got .*\)$", ")", msg)
                msg = re.sub(r" \(the graph has .*\)$|; \d+ and \d+\)$| \(\d+ and \d+ rows\)$", lambda m: ")" if m.group(0).startswith(";") else "", msg)
            print(f"{C['c']}│{C['x']}  {C['g'] + '✓' if ok else C['r'] + '✗'}{C['x']} {msg}", flush=True)
    except Unfinished as e:
        results.append(False)
        print(f"{C['c']}│{C['x']}  {C['r']}✗{C['x']} {e}")
    except Exception as e:  # a half-finished task shouldn't crash the checker
        results.append(False)
        msg = getattr(e, "message", None) or str(e)
        print(f"{C['c']}│{C['x']}  {C['r']}✗{C['x']} {type(e).__name__}: {msg.splitlines()[0][:160] if msg else ''}")
    passed = sum(results)
    done = passed == len(results)
    tail = f"{C['g']}verified{C['x']}" if done else f"{C['y']}stuck?{C['x']} make solve T={t}  {C['d']}·  {GUIDE}/task-{t.replace('.', '-')}/{C['x']}"
    print(f"{C['c']}╰─{C['x']} {passed}/{len(results)} checks passed  {tail}\n")
    return done


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "--files":
        print(" ".join(TASKS.get(sys.argv[2], ("", []))[1]))
        sys.exit(0)
    if arg == "--files-before":
        ch = int(sys.argv[2])
        print(" ".join(sorted({f for t, (_, fs) in TASKS.items() if int(t.split(".")[0]) < ch for f in fs})))
        sys.exit(0)
    if arg.startswith("ch"):
        n = int(arg[2:])
        print(f"{C['b']}chapter {n} · {CHAPTERS[n]}{C['x']}\n")
        sys.exit(0 if all([report(t) for t in TASKS if t.startswith(f"{n}.")]) else 1)
    if arg == "all":
        done = [t for t in TASKS if report(t)]
        print(f"{C['b']}{len(done)}/{len(TASKS)} tasks verified{C['x']}")
        sys.exit(0 if len(done) == len(TASKS) else 1)
    if arg not in TASKS:
        sys.exit(f"no task {arg}: tasks are {', '.join(TASKS)}")
    sys.exit(0 if report(arg) else 1)
