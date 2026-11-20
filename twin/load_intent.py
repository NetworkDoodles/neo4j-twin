"""make load · task 2.2: the intent (fabric/intent.yml) and the business (fabric/services.yml), into the graph.

    python twin/load_intent.py

This is the intended side of the twin: what the network is meant to be. Chapter 3 adds what it actually is.

The load has to give the same graph however many times it runs, because it will run every time the intent
changes. So every node and relationship goes in with MERGE ("find it, or create it"), never CREATE, and the
properties go in with SET, so a changed value is updated in place. Values travel as parameters ($rows), never
pasted into the query text: Neo4j can reuse a parameterized query's plan, and a name with a quote in it can't
turn into Cypher.

Each query gets a whole list at once and walks it with UNWIND: one round trip per kind of thing, not one per row.
"""
import ipaddress
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
from lib import fabric, twin  # noqa: E402

SERVICES = ROOT / "fabric" / "services.yml"


def rows(intent, services):
    """The two files flattened into lists of plain dicts, one list per kind of thing. No Cypher here."""
    site = intent["fabric"]["site"]
    devices = [{"name": n, "site": site, "role": d["role"], "asn": fabric.asn(intent, n), "mgmt": d["mgmt"],
                "loopback": d["loopback"]} for n, d in intent["devices"].items()]
    interfaces, hosts = [], []
    for dev, ports in fabric.interfaces(intent).items():
        for port, p in ports.items():
            net = ipaddress.ip_interface(p["address"]).network
            interfaces.append({"id": f"{dev}:{port}", "device": dev, "name": port, "ip": p["address"], "subnet": str(net)})
    for dev, d in intent["devices"].items():
        for h in d.get("hosts", []):
            net = ipaddress.ip_network(h["subnet"])
            interfaces.append({"id": f"{dev}:{h['port']}", "device": dev, "name": h["port"],
                               "ip": f"{h['gateway']}/{net.prefixlen}", "subnet": str(net)})
            hosts.append({"name": h["host"], "ip": f"{h['address']}/{net.prefixlen}", "port": f"{dev}:{h['port']}"})
    links = [{"a": l["a"], "b": l["b"]} for l in intent["links"]]
    apps = [{"name": n, "host": a["host"]} for n, a in services["apps"].items()]
    flows = [dict(f) for f in services["flows"]]
    svcs = [{"key": k, "name": s["name"], "owner": s["owner"], "tier": s["tier"], "needs": s["needs"]}
            for k, s in services["services"].items()]
    return {"devices": devices, "interfaces": interfaces, "links": links, "hosts": hosts, "apps": apps,
            "flows": flows, "services": svcs}


def load_network(tx, data):
    """Sites, devices, interfaces, subnets and cabling."""
    tx.run("""
        UNWIND $rows AS d
        MERGE (s:Site {name: d.site})
        MERGE (dev:Device {name: d.name})
        SET dev.role = d.role, dev.asn = d.asn, dev.mgmt = d.mgmt, dev.loopback = d.loopback
        MERGE (dev)-[:LOCATED_IN]->(s)
    """, rows=data["devices"])
    # TODO 2.2a  (follow along) The interfaces, then the cabling.
    #            For each row in data["interfaces"] ({id, device, name, ip, subnet}): MERGE the Interface on its id,
    #            SET its device, name and ip, and MERGE (device)-[:HAS_INTERFACE]->(interface) and
    #            (interface)-[:IN_SUBNET]->(:Subnet {prefix}).
    #            Then for each row in data["links"] ({a, b}, two interface ids): MATCH both interfaces and MERGE
    #            one CABLED_TO from a to b.
    # >>> solution
    tx.run("""
        UNWIND $rows AS i
        MATCH (d:Device {name: i.device})
        MERGE (n:Interface {id: i.id})
        SET n.device = i.device, n.name = i.name, n.ip = i.ip
        MERGE (d)-[:HAS_INTERFACE]->(n)
        MERGE (s:Subnet {prefix: i.subnet})
        MERGE (n)-[:IN_SUBNET]->(s)
    """, rows=data["interfaces"])
    tx.run("""
        UNWIND $rows AS l
        MATCH (a:Interface {id: l.a}), (b:Interface {id: l.b})
        MERGE (a)-[:CABLED_TO]->(b)
    """, rows=data["links"])
    # <<< solution


def load_services(tx, data):
    """Hosts, the apps on them, the flows between apps, and the business services that need the apps."""
    # TODO 2.2b  (challenge) Four UNWINDs, the same way:
    #            hosts    {name, ip, port}: MERGE (:Host {name}), SET ip, MERGE (host)-[:ATTACHED_TO]->(its leaf port)
    #            apps     {name, host}: MERGE (:App {name}) and (app)-[:RUNS_ON]->(host)
    #            flows    {from, to, port, proto}: (a)-[:TALKS_TO {port}]->(b), with proto SET on it
    #            services {key, name, owner, tier, needs}: MERGE (:Service {name}), SET key, owner and tier, and one
    #                     DEPENDS_ON to each app in needs (UNWIND s.needs inside the same query)
    # >>> solution | pass  # TODO 2.2b (challenge): not done yet
    tx.run("""
        UNWIND $rows AS h
        MATCH (port:Interface {id: h.port})
        MERGE (n:Host {name: h.name})
        SET n.ip = h.ip
        MERGE (n)-[:ATTACHED_TO]->(port)
    """, rows=data["hosts"])
    tx.run("""
        UNWIND $rows AS a
        MATCH (h:Host {name: a.host})
        MERGE (n:App {name: a.name})
        MERGE (n)-[:RUNS_ON]->(h)
    """, rows=data["apps"])
    tx.run("""
        UNWIND $rows AS f
        MATCH (a:App {name: f.from}), (b:App {name: f.to})
        MERGE (a)-[t:TALKS_TO {port: f.port}]->(b)
        SET t.proto = f.proto
    """, rows=data["flows"])
    tx.run("""
        UNWIND $rows AS s
        MERGE (n:Service {name: s.name})
        SET n.key = s.key, n.owner = s.owner, n.tier = s.tier
        WITH n, s
        UNWIND s.needs AS need
        MATCH (a:App {name: need})
        MERGE (n)-[:DEPENDS_ON]->(a)
    """, rows=data["services"])
    # <<< solution


def main(intent_path=fabric.INTENT, services_path=SERVICES):
    data = rows(fabric.load(intent_path), yaml.safe_load(pathlib.Path(services_path).read_text()))
    with twin.driver() as d, d.session() as s:
        # Chapter 1's hand-drawn links aren't part of this schema: the cabling is CABLED_TO between interfaces.
        s.run("MATCH ()-[r:LINK]->() DELETE r").consume()
        # One transaction for the whole load: if any query fails, none of it is kept.
        s.execute_write(lambda tx: (load_network(tx, data), load_services(tx, data)))
    c = twin.counts()
    keys = ["Site", "Device", "Interface", "Subnet", "Host", "App", "Service"]
    rels = ["HAS_INTERFACE", "CABLED_TO", "IN_SUBNET", "ATTACHED_TO", "RUNS_ON", "TALKS_TO", "DEPENDS_ON"]
    print("  nodes:         " + ", ".join(f"{c.get(k, 0)} {k}" for k in keys))
    print("  relationships: " + ", ".join(f"{c.get(k, 0)} {k}" for k in rels))


if __name__ == "__main__":
    main(*sys.argv[1:3])
