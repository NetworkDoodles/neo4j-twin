"""task 6.2: a read-only MCP server over the graph twin, so an AI agent can ask it questions.

    python twin/mcp_server.py          serves MCP on stdio (an MCP client, like Claude Code, starts it)
    python lab/ask.py                  calls every tool once, the way an agent would (make run T=6.2)

Three tools. Two are questions you already wrote as queries, with their parameters filled in by the agent:

    blast_radius(device)     queries/blast-radius.cypher (task 5.1)
    path(src, dst)           queries/path.cypher (task 4.1)

The third lets the agent write its own Cypher, which is the useful one and the dangerous one:

    cypher(query, params)    any read-only query, at most MAX_ROWS rows, stopped after TIMEOUT seconds

Read-only is enforced by Neo4j, not by checking the query's text: every tool runs inside a READ transaction
(session.execute_read), and Neo4j refuses a write in one, however it's spelled. The timeout and the row limit keep
one bad query from tying up the graph or flooding the agent's context.

Register it with an MCP client by command: `python twin/mcp_server.py`, with the lab's venv's python.
"""
import pathlib
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from neo4j import unit_of_work
from neo4j.exceptions import Neo4jError

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
from lib import twin  # noqa: E402

MAX_ROWS = 100
TIMEOUT = 10      # seconds; the server's own limit (docker-compose.yml) is 30
mcp = FastMCP("network-twin", instructions=(
    "A read-only graph twin of the dc1 fabric: devices, interfaces, cabling (intent), LLDP and BGP (observed), "
    "hosts, apps, the flows between them, and the business services that depend on them."))


def query_file(name):
    text = (ROOT / "queries" / name).read_text()
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("//")).strip().rstrip(";")


def read(text, params=None, limit=MAX_ROWS):
    """Run one query in a READ transaction, with a timeout. Returns at most `limit` rows as dicts."""
    # TODO 6.2a  (follow along) Open a session on twin.driver() and run the query with session.execute_read(work),
    #            where work(tx) runs the query with its params and returns [record.data() for record in
    #            result.fetch(limit)]. Decorate work with @unit_of_work(timeout=TIMEOUT): that's how a transaction
    #            function gets a timeout.
    #            A Neo4jError (a refused write, a syntax error, a timeout) becomes ToolError(e.message), which the
    #            agent sees as the tool's error instead of the server crashing.
    # >>> solution
    @unit_of_work(timeout=TIMEOUT)
    def work(tx):
        result = tx.run(text, params or {})
        return [r.data() for r in result.fetch(limit)]
    try:
        with twin.driver() as d, d.session() as s:
            return s.execute_read(work)
    except Neo4jError as e:
        raise ToolError(e.message) from e
    # <<< solution


@mcp.tool
def blast_radius(device: str) -> list[dict]:
    """If this device (a switch name like leaf1) fails, which business services lose which flows."""
    return read(query_file("blast-radius.cypher"), {"device": device})


@mcp.tool
def path(src: str, dst: str) -> list[dict]:
    """The switches on the shortest path between two hosts (host1 .. host4)."""
    return read(query_file("path.cypher"), {"from": src, "to": dst})


# TODO 6.2b  (challenge) The third tool: cypher(query: str, params: dict | None = None) -> list[dict], decorated
#            with @mcp.tool like the two above, that runs the agent's own query through read(). Its docstring is
#            what the agent reads to decide how to use it: say it's read-only, name the labels and relationship
#            types it can use, and the row limit.
# >>> solution | # TODO 6.2b (challenge): the cypher tool goes here
@mcp.tool
def cypher(query: str, params: dict | None = None) -> list[dict]:
    """Run your own read-only Cypher query against the graph twin. At most 100 rows; writes are refused.
    Labels: Site, Device, Interface, Subnet, Host, App, Service. Relationships: LOCATED_IN, HAS_INTERFACE,
    CABLED_TO (intended cabling), IN_SUBNET, ATTACHED_TO (host to leaf port), RUNS_ON, TALKS_TO {port, proto},
    DEPENDS_ON, LLDP_NEIGHBOR {seen_at} and BGP_PEER {state, prefixes, seen_at, last_seen} (observed).
    Pass values as params ($name in the query), not pasted into it."""
    return read(query, params)
# <<< solution


if __name__ == "__main__":
    mcp.run()
