"""The lab's way into Neo4j, the graph twin: a driver, a wait, and a few helpers the checker uses.

The address and the password are the lab's own (docker-compose.yml). NEO4J_URI and NEO4J_PASSWORD override them.
Lab credentials only: a real graph's password comes from a vault or your shell.
"""
import os
import time

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "lab-twin-graph"))


def driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(URI, auth=AUTH)


def wait(timeout=180):
    """Wait until Neo4j answers a query (it takes 15 to 30 seconds to start). Exits if it never does."""
    from neo4j.exceptions import ServiceUnavailable, AuthError
    deadline = time.time() + timeout
    while True:
        try:
            with driver() as d:
                d.verify_connectivity()
                return True
        except (ServiceUnavailable, AuthError, OSError):
            if time.time() > deadline:
                raise SystemExit("Neo4j didn't answer in time: docker logs neo4j says why, make up starts it")
            time.sleep(3)


def rows(query, **params):
    """Run one query and return its records as a list of dicts."""
    with driver() as d:
        records, _, _ = d.execute_query(query, params)
        return [r.data() for r in records]


def one(query, **params):
    r = rows(query, **params)
    return next(iter(r[0].values())) if r else None


def counts():
    """{"Device": n, ..., "CABLED_TO": n, ...}: every label and relationship type in the graph and how many."""
    out = {}
    for r in rows("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c"):
        out[r["l"]] = r["c"]
    for r in rows("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c"):
        out[r["t"]] = r["c"]
    return out


def fingerprint():
    """Everything in the graph as one sorted list of strings: equal fingerprints, equal graphs."""
    nodes = rows("MATCH (n) RETURN labels(n) AS l, properties(n) AS p")
    rels = rows("MATCH (a)-[r]->(b) RETURN type(r) AS t, properties(r) AS p, elementId(a) AS a, elementId(b) AS b, "
                "properties(a) AS pa, properties(b) AS pb")
    out = [f"N {sorted(n['l'])} {sorted(n['p'].items())}" for n in nodes]
    out += [f"R {r['t']} {sorted(r['p'].items())} {sorted(r['pa'].items())} {sorted(r['pb'].items())}" for r in rels]
    return sorted(out)


def wipe():
    rows("MATCH (n) DETACH DELETE n")
