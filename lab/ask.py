"""make run T=6.2 · call the MCP server's tools the way an agent would, and show what comes back.

It runs twin/mcp_server.py in this process (fastmcp's in-memory client), so there's nothing to start first. The
last call tries to write through the cypher tool, which is the point: it has to be refused.
"""
import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, (ROOT / "twin").as_posix())

from fastmcp import Client  # noqa: E402

CALLS = [
    ("blast_radius", {"device": "leaf1"}),
    ("path", {"src": "host1", "dst": "host2"}),
    ("cypher", {"query": "MATCH (s:Service)-[:DEPENDS_ON]->(a:App)-[:RUNS_ON]->(h:Host) "
                         "RETURN s.name AS service, a.name AS app, h.name AS host ORDER BY service, app"}),
    ("cypher", {"query": "MATCH (d:Device {name: $name}) SET d.role = 'changed' RETURN d.name", "params": {"name": "spine1"}}),
]


async def ask(calls=CALLS):
    import logging
    import mcp_server
    # the server logs every tool error to the terminal; this script prints them itself
    logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
    out = []
    async with Client(mcp_server.mcp) as c:
        tools = [t.name for t in await c.list_tools()]
        out.append(("tools", tools))
        for name, args in calls:
            r = await c.call_tool(name, args, raise_on_error=False)
            if r.is_error:
                out.append((name, args, "error", " ".join(b.text for b in r.content if hasattr(b, "text"))))
            else:
                out.append((name, args, "ok", r.structured_content.get("result") if r.structured_content else r.data))
    return out


def main():
    out = asyncio.run(ask())
    print(f"  tools: {', '.join(out[0][1])}")
    for name, args, status, value in out[1:]:
        print(f"\n  {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
        if status == "error":
            print(f"  ✗ error: {value}")
        else:
            for row in value:
                print("    " + json.dumps(row))


if __name__ == "__main__":
    main()
