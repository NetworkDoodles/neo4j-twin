# Lab · Graph digital twins with Neo4j

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/NetworkDoodles/neo4j-twin?quickstart=1)

Companion to [Graph digital twins with Neo4j](https://networkdoodles.com/lessons/neo4j/) by David Henderson.
One chapter per lesson.

A graph twin is a model of the network as what's connected to what. It doesn't forward packets. It answers
questions about the network fast, and in the network's own terms: what's on the path from host1 to host2, what
the intent says that LLDP doesn't see, which business service goes down if leaf1 does.

Here you build one in [Neo4j](https://neo4j.com/) for a six-switch spine/leaf fabric. You draw the fabric by
hand first. Then you load it from its intent, read the switches' live state through their command API next to
that intent, and ask the graph questions in Cypher: paths, ECMP, drift, blast radius, single points of failure.
You also run what-ifs inside a transaction that's rolled back, keep the twin current, and give an AI agent
read-only access to it through an MCP server.

**Step-by-step guide:** https://networkdoodles.com/labs/neo4j-twin/
**New to VS Code or the terminal?** https://networkdoodles.com/labs/basics/ walks through all of it, with screenshots.

## The switches

The switches run **CapeOS Pulse**, an open-source lab network OS with an EOS-style CLI and a JSON-RPC
command API. Chapter 3's collector reads LLDP, interface status and BGP through that API: the same JSON-RPC call
and the same JSON shapes you'd get from an EOS switch's eAPI.

## Start here: Codespaces

1. Click the **Open in GitHub Codespaces** badge at the top, sign in to GitHub (a free account is fine) and click **Create new codespace**.
2. VS Code asks **Do you trust the authors of the files in this folder?** Click **Trust Folder & Continue**:
   the lab runs its own scripts, so VS Code wants your OK once per codespace.
3. Wait about 5 minutes for the first build. VS Code opens in your browser and starts the fabric and Neo4j; the
   **Lab status** terminal shows the six switches and Neo4j with green check marks when they're ready.
4. In a terminal: `make check T=1.1`. Then follow the guide.

It runs on **your own** GitHub account's free monthly allowance: 120 core-hours, and the lab's 4-core machine
uses about 10 of them. Idle codespaces stop after 30 minutes. Stopped ones still use storage, so delete yours
at [github.com/codespaces](https://github.com/codespaces) when you've finished.

You need about an hour per chapter, and no licenses.

## Advanced: run it on your laptop

Same dev container, on your own Docker. You need Docker (Desktop, OrbStack, Colima or Docker Engine) with
8 GB of memory, Git, and VS Code with the Dev Containers extension. The switch image is built for both
Intel and Apple silicon.

```bash
git clone https://gitlab.com/networkdoodles-labs/neo4j-twin.git
cd neo4j-twin
code .             # then "Reopen in Container"
```

## What's where

```
fabric/intent.yml      the fabric as we mean it to be: switches, roles, addresses, links, hosts
fabric/services.yml    what runs on it: apps on hosts, the flows between them, the business services
cypher/fabric.cypher   chapter 1: the fabric drawn by hand
queries/               your Cypher questions, one file each (make cypher F=... P='name=value')
graph/schema.cypher    chapter 2: constraints and indexes
twin/                  your Python: the loaders, the collector, the what-if, the change report, the MCP server
changes/               chapter 5: changes to try in a what-if (make whatif C=...)
lab/                   the lab itself: topology, startup configs, faults, the Cypher runner
build/snapshots/       chapter 3 on: what the switches said, one folder per collection
```

## Commands

```bash
make help          # everything
make check T=1.2   # verify a task (CH=1 for a chapter, nothing for the whole lab)
make solve T=1.2   # stuck? copy that task's finished files from the solution branch
make skip CH=4     # start at any chapter
make shell         # cypher-shell, Neo4j's own command line
make refresh       # collect from the switches, load it, and say what changed
make break X=link  # break the fabric on purpose; make fix puts it back
```

Neo4j's browser is at http://localhost:7474 (user `neo4j`, password `lab-twin-graph`). In Codespaces, open it
from the **Ports** tab. These are lab credentials, never real ones.

## License

MIT. Neo4j Community Edition is GPLv3, and CapeOS is open source.
