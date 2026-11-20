# neo4j-twin: facts for the lessons

Everything here comes from the lab's own files and from real runs (dev container image built from
.devcontainer/Dockerfile, run with `docker run --privileged` on Docker Desktop, 2026-11-20 UTC). Times are from
those runs; Codespaces is untested.

## Schema (final)

Neo4j 5.26.32 community. Community edition has uniqueness constraints only (no node keys, no property existence
constraints), so every node a load MERGEs on has one unique property.

### Nodes

| Label | Properties | Unique on | Comes from |
|---|---|---|---|
| `Site` | `name` | `name` | intent (`fabric.site`: dc1) |
| `Device` | `name`, `role` (spine/leaf), `asn`, `mgmt`, `loopback`; observed: `observed_at` | `name` | intent |
| `Interface` | `id` ("leaf1:Ethernet1"), `device`, `name`, `ip` (address/len); observed: `oper_status`, `observed_at` | `id` | intent |
| `Subnet` | `prefix` ("10.0.11.0/31", "10.10.1.0/24") | `prefix` | intent |
| `Host` | `name`, `ip` | `name` | intent |
| `App` | `name` | `name` | fabric/services.yml |
| `Service` | `name` ("Online orders"), `key` ("online-orders"), `owner`, `tier` | `name` | fabric/services.yml |

Plus one index: `Interface(device)`.

### Relationships

| Type | From → to | Properties | Side |
|---|---|---|---|
| `LOCATED_IN` | Device → Site | | intent |
| `HAS_INTERFACE` | Device → Interface | | intent |
| `CABLED_TO` | Interface → Interface | | intent, stored once per link (the intent's `a` end → `b` end) |
| `IN_SUBNET` | Interface → Subnet | | intent |
| `ATTACHED_TO` | Host → Interface (the leaf's port) | | intent |
| `RUNS_ON` | App → Host | | services.yml |
| `TALKS_TO` | App → App | `port`, `proto` | services.yml |
| `DEPENDS_ON` | Service → App | | services.yml |
| `LLDP_NEIGHBOR` | Interface → Interface (the reporting switch's port → the neighbor's port) | `seen_at` | observed, one per switch that reports it (so two per healthy link) |
| `BGP_PEER` | Device → Device (the reporting switch → its peer) | `state`, `prefixes`, `seen_at`, `last_seen` | observed, one per switch that reports it |

Meaning of the timestamps (ISO 8601 UTC strings, the snapshot's collection time):

- `observed_at` (Device, Interface): the last collection that read this switch.
- `seen_at` (LLDP_NEIGHBOR, BGP_PEER): the last collection that reported this relationship. A relationship whose
  `seen_at` is older than its device's `observed_at` was not reported last time; the load removes those.
- `last_seen` (BGP_PEER only): the last collection in which the session was `Established`. A session that is up
  has `last_seen = seen_at`; one that went down keeps the time it was last up.

### Constraints

```cypher
CREATE CONSTRAINT site_name IF NOT EXISTS FOR (s:Site) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT device_name IF NOT EXISTS FOR (d:Device) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT interface_id IF NOT EXISTS FOR (i:Interface) REQUIRE i.id IS UNIQUE;
CREATE CONSTRAINT subnet_prefix IF NOT EXISTS FOR (s:Subnet) REQUIRE s.prefix IS UNIQUE;
CREATE CONSTRAINT host_name IF NOT EXISTS FOR (h:Host) REQUIRE h.name IS UNIQUE;
CREATE CONSTRAINT app_name IF NOT EXISTS FOR (a:App) REQUIRE a.name IS UNIQUE;
CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;
CREATE INDEX interface_device IF NOT EXISTS FOR (i:Interface) ON (i.device);
```

### The business story (fabric/services.yml)

| App | Host | Leaf |
|---|---|---|
| web-shop | host2 | leaf4 |
| orders-db | host1 | leaf1 |
| payments | host4 | leaf3 |
| netmon | host3 | leaf2 |

Flows: web-shop → orders-db (5432/tcp), web-shop → payments (443/tcp), netmon → web-shop (443/tcp, synthetic checks).
Services: "Online orders" (ecommerce, tier 1) depends on web-shop, orders-db, payments. "Network monitoring"
(netops, tier 3) depends on netmon.

The two spines are identical in the intent: no single spine is in any service's blast radius. Each leaf is (every
host is single-homed). Chapter 5's what-if takes one link away (spine2–leaf1, orders-db's leaf): after that, spine1
is a single point of failure for Online orders, which the healthy graph doesn't show.

Chapter 1 is a hand-drawn warm-up, not this schema: `(:Device {name, role, asn})-[:LINK]->(:Device)`. The chapter 2
load deletes the `LINK` relationships.

## Versions

| | |
|---|---|
| Switches | CapeOS Pulse 0.11.2 (`ghcr.io/dkhenderson2/capeos-pulse:0.11.2`), containerlab 0.82.0 |
| Neo4j | `neo4j:5.26.32-community` (5.26 LTS), heap 512 MB, page cache 128 MB, container limit 1 GB, `db.transaction.timeout` 30 s |
| Python | 3.13, neo4j driver 6.4.1, httpx 0.28.1, fastmcp 4.2.2, PyYAML 6.0.3, Jinja2 3.1.6 |
| Dev container | `ghcr.io/srl-labs/containerlab/devcontainer-dind-slim:0.82.0`, 4 cores, 8 GB |
| Lab addresses | management 172.80.91.0/24 (spines .11/.12, leaves .21-.24, hosts .31-.34); fabric /31s 10.0.11.0/31 ... 10.0.24.0/31; host subnets 10.10.1-4.0/24 (gateway .1, host .10); loopbacks 10.255.0.x |
| Credentials | switches admin / capeos-lab; Neo4j neo4j / lab-twin-graph. Lab only. |

Memory in use with everything up: Neo4j 640 MB, each switch 96-109 MB, each host about 1 MB.

## Files the learner edits, per task

| Task | Files | Run | TODOs |
|---|---|---|---|
| 1.1 the fabric by hand | `cypher/fabric.cypher` | `make cypher F=cypher/fabric.cypher` | a: spine2, leaf1, leaf1's two LINKs · b: leaf2-4 and their six LINKs |
| 1.2 first questions | `queries/neighbors.cypher`, `queries/links-per-device.cypher` | `make cypher F=queries/neighbors.cypher P='device=leaf1'` | a: neighbors · b: links per device |
| 2.1 the schema | `graph/schema.cypher` | `make cypher F=graph/schema.cypher` | a: Device.name, Interface.id, index on Interface(device) · b: Site, Subnet, Host, App, Service |
| 2.2 an idempotent load | `twin/load_intent.py` | `make load` | a: interfaces (+ HAS_INTERFACE, IN_SUBNET) and CABLED_TO · b: hosts, apps, flows, services |
| 3.1 collect a snapshot | `twin/collect.py` | `make collect` | a: the JSON-RPC request and the lldp/interfaces commands · b: the BGP command |
| 3.2 observed state | `twin/load_state.py` | `python twin/load_state.py` | a: oper_status and LLDP_NEIGHBOR · b: BGP_PEER, found by peer IP |
| 4.1 paths and ECMP | `queries/path.cypher`, `queries/ecmp.cypher` | `make cypher F=queries/path.cypher P='from=host1 to=host2'` | a: shortestPath · b: allShortestPaths |
| 4.2 drift | `queries/drift-links.cypher`, `queries/drift-bgp.cypher` | `make cypher F=queries/drift-links.cypher` | a: cabling vs LLDP · b: implied sessions vs BGP_PEER |
| 5.1 blast radius | `queries/blast-radius.cypher`, `queries/spof.cypher` | `make cypher F=queries/blast-radius.cypher P='device=leaf1'` | a: one device · b: every device, tier 1 |
| 5.2 what-if | `twin/whatif.py` | `make whatif C=lose-spine2-leaf1` | a: apply the change in the transaction · b: flows broken now |
| 6.1 what changed | `twin/changes.py` | `make refresh` | a: LLDP gone/appeared · b: BGP state changes |
| 6.2 an MCP server | `twin/mcp_server.py` | `python lab/ask.py` (`make run T=6.2`) | a: read() in a READ transaction with a timeout and row limit · b: the cypher tool |

Provided, not edited: `lab/cypher.py` (the .cypher runner behind `make cypher`), `lab/ask.py` (in-memory MCP
client), `lab/faults.py` (`make break X=link|bgp`, `make fix`), `lab/wipe.py` (`make wipe`), `lib/twin.py` (driver,
counts, fingerprint), `changes/*.yml` (three what-ifs).

## Makefile targets

`help setup images up down reset wipe ssh shell cypher load collect refresh whatif mcp break fix status run check
solve skip`. `make shell` is cypher-shell inside the neo4j container. `make load` = schema.cypher, then
load_intent.py. `make refresh` = collect.py, load_state.py, changes.py. `make up` deploys containerlab, starts Neo4j
with docker compose, then waits for every switch, every BGP session and Neo4j: about a minute and a half.

## The solutions' Cypher, exactly

### 1.1 (cypher/fabric.cypher)

```cypher
MATCH (n) DETACH DELETE n;
CREATE
    (spine1:Device {name: "spine1", role: "spine", asn: 65000})
  , (spine2:Device {name: "spine2", role: "spine", asn: 65000})
  , (leaf1:Device {name: "leaf1", role: "leaf", asn: 65001})
  , (leaf1)-[:LINK]->(spine1)
  , (leaf1)-[:LINK]->(spine2)
  , (leaf2:Device {name: "leaf2", role: "leaf", asn: 65002})
  ...
  , (leaf4)-[:LINK]->(spine2)
;
```
Output: `nodes created: 6, relationships created: 8, properties set: 18, labels added: 6`.

### 1.2

```cypher
MATCH (d:Device {name: $device})-[:LINK]-(n:Device)
RETURN n.name AS neighbor
ORDER BY neighbor;

MATCH (d:Device)-[l:LINK]-()
RETURN d.name AS device, d.role AS role, count(l) AS links
ORDER BY links DESC, device;
```
leaf1 → spine1, spine2. Links: spine1 4, spine2 4, leaf1-4 2 each.

### 2.1: the constraints in the Schema section above.

### 2.2 (twin/load_intent.py, the queries)

```cypher
UNWIND $rows AS d
MERGE (s:Site {name: d.site})
MERGE (dev:Device {name: d.name})
SET dev.role = d.role, dev.asn = d.asn, dev.mgmt = d.mgmt, dev.loopback = d.loopback
MERGE (dev)-[:LOCATED_IN]->(s)

UNWIND $rows AS i
MATCH (d:Device {name: i.device})
MERGE (n:Interface {id: i.id})
SET n.device = i.device, n.name = i.name, n.ip = i.ip
MERGE (d)-[:HAS_INTERFACE]->(n)
MERGE (s:Subnet {prefix: i.subnet})
MERGE (n)-[:IN_SUBNET]->(s)

UNWIND $rows AS l
MATCH (a:Interface {id: l.a}), (b:Interface {id: l.b})
MERGE (a)-[:CABLED_TO]->(b)

UNWIND $rows AS h
MATCH (port:Interface {id: h.port})
MERGE (n:Host {name: h.name})
SET n.ip = h.ip
MERGE (n)-[:ATTACHED_TO]->(port)

UNWIND $rows AS a
MATCH (h:Host {name: a.host})
MERGE (n:App {name: a.name})
MERGE (n)-[:RUNS_ON]->(h)

UNWIND $rows AS f
MATCH (a:App {name: f.from}), (b:App {name: f.to})
MERGE (a)-[t:TALKS_TO {port: f.port}]->(b)
SET t.proto = f.proto

UNWIND $rows AS s
MERGE (n:Service {name: s.name})
SET n.key = s.key, n.owner = s.owner, n.tier = s.tier
WITH n, s
UNWIND s.needs AS need
MATCH (a:App {name: need})
MERGE (n)-[:DEPENDS_ON]->(a)
```
All seven run in one `session.execute_write` (one transaction). Before it, the loader deletes chapter 1's `LINK`s.
Interface `ip` is the address with its length: leaf1:Ethernet1 is `10.0.11.1/31`; a leaf's host port has the
gateway, leaf1:Ethernet3 `10.10.1.1/24`. Host `ip` is `10.10.1.10/24`.

Result, and the same on every run:
```
  nodes:         1 Site, 6 Device, 20 Interface, 12 Subnet, 4 Host, 4 App, 2 Service
  relationships: 20 HAS_INTERFACE, 8 CABLED_TO, 20 IN_SUBNET, 4 ATTACHED_TO, 4 RUNS_ON, 3 TALKS_TO, 4 DEPENDS_ON
```
49 nodes and 69 relationships in all (the 6 LOCATED_IN aren't in the printout). The checker proves idempotency by fingerprinting every node and
relationship with its properties before and after a second load. Gap worth saying in the lesson: the loader only
adds and updates. Something removed from the intent stays in the graph until you delete it; the lab doesn't prune
the intent side (it does prune the observed side, 3.2).

### 3.1 (twin/collect.py)

The request, to `https://<mgmt>/command-api`, basic auth, `verify=False`, 10 s timeout:
```json
{"jsonrpc": "2.0", "method": "runCmds", "id": 1,
 "params": {"version": 1, "cmds": ["show lldp neighbors", "show interfaces status", "show ip bgp summary"], "format": "json"}}
```
CapeOS Pulse 0.11.2 answers all three in EOS eAPI shapes: `lldpNeighbors[]` with `port`, `neighborDevice`,
`neighborPort`, `ttl`; `interfaceStatuses{}` with `linkStatus` ("connected"), `lineProtocolStatus` ("up"/"down"),
`description`; `vrfs.default.peers{<ip>}` with `peerState`, `prefixAccepted`, `prefixReceived`, `description`
(the peer's name, from the config), `asn`, `upDownTime`. Hosts are Alpine containers with no LLDP, so leaf
Ethernet3 has no neighbor. No CapeOS gaps hit.

Real leaf1 reply to `show lldp neighbors`:
```json
{"jsonrpc": "2.0", "id": 1, "result": [{"lldpNeighbors": [{"port": "Ethernet1", "neighborDevice": "spine1", "neighborPort": "Ethernet1", "ttl": 120}, {"port": "Ethernet2", "neighborDevice": "spine2", "neighborPort": "Ethernet1", "ttl": 120}], "tablesLastChangeTime": 1795148070.2441, "tablesInserts": 2, "tablesDeletes": 0, "tablesDrops": 0, "tablesAgeOuts": 0}]}
```
Timing: all six switches in parallel (one thread each), 0.11 to 0.34 s per collection over a dozen runs.
Snapshot: `build/snapshots/20261120T041516Z/{spine1,...,leaf4}.json` plus `meta.json`
(`collected_at`, `switches`, `failed`, `seconds`). One switch failing doesn't stop the other five.

### 3.2 (twin/load_state.py)

```cypher
UNWIND $rows AS row
MATCH (i:Interface {id: row.id})
SET i.oper_status = row.status, i.observed_at = $at

UNWIND $rows AS row
MATCH (a:Interface {id: row.from}), (b:Interface {id: row.to})
MERGE (a)-[r:LLDP_NEIGHBOR]->(b)
SET r.seen_at = $at

UNWIND $rows AS row
MATCH (d:Device {name: row.device})
MATCH (p:Device)-[:HAS_INTERFACE]->(i:Interface)
WHERE split(i.ip, "/")[0] = row.peer_ip
MERGE (d)-[r:BGP_PEER]->(p)
SET r.state = row.state, r.prefixes = row.prefixes, r.seen_at = $at,
    r.last_seen = CASE WHEN row.state = "Established" THEN $at ELSE r.last_seen END
```
Then (provided) the prune: LLDP_NEIGHBOR and BGP_PEER from a switch in this snapshot whose `seen_at <> $at` are
deleted and printed, and `Device.observed_at = $at`. The BGP peer is found by address, joining observed state to
the intent's interface addresses: the switch names its peer by IP (10.0.11.0), not by name.

Result: `16 LLDP_NEIGHBOR, 16 BGP_PEER (16 Established)`, all 20 interfaces `up`. leaf1's BGP_PEERs: spine1 and
spine2, Established, 7 prefixes each, `seen_at = last_seen`.

### 4.1

```cypher
MATCH (a:Host {name: $from}), (b:Host {name: $to})
MATCH p = shortestPath((a)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(b))
RETURN [n IN nodes(p) WHERE n:Device | n.name] AS hops;

MATCH (a:Host {name: $from}), (b:Host {name: $to})
MATCH p = allShortestPaths((a)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(b))
WITH p, [n IN nodes(p) WHERE n:Device AND n.role = "spine" | n.name][0] AS spine
ORDER BY spine
RETURN count(p) AS paths, collect(spine) AS via;
```
host1 → host2: hops `['leaf1', 'spine1', 'leaf4']`; 2 paths via `['spine1', 'spine2']`. Without the spine2-leaf4
cable (deleted in a rolled-back transaction by the checker): 1 path via spine1. A host-to-host shortest path is 10
relationships long (host, leaf port, leaf, uplink, spine port, spine, spine port, leaf port, leaf, leaf port, host).
Each query runs in well under a second (`make run T=4.1` 0.57 s wall, including Python start-up).

### 4.2

```cypher
MATCH (a:Interface)-[:CABLED_TO]->(b:Interface)
WHERE NOT (a)-[:LLDP_NEIGHBOR]->(b) OR NOT (b)-[:LLDP_NEIGHBOR]->(a)
RETURN a.id AS cabled, b.id AS to, a.oper_status AS a_status, b.oper_status AS b_status
ORDER BY cabled;

MATCH (d:Device)-[:HAS_INTERFACE]->(:Interface)-[:CABLED_TO]-(:Interface)<-[:HAS_INTERFACE]-(p:Device)
OPTIONAL MATCH (d)-[r:BGP_PEER]->(p)
WITH d, p, r
WHERE r IS NULL OR r.state <> "Established"
RETURN d.name AS device, p.name AS peer, coalesce(r.state, "missing") AS state, r.last_seen AS last_up
ORDER BY device, peer;
```
Healthy: 0 rows each. `make break X=link` (spine2 shuts Ethernet1), wait 5 s, collect, load:
```
  loaded build/snapshots/20261120T041523Z (2026-11-20T04:15:23Z): 14 LLDP_NEIGHBOR, 16 BGP_PEER (14 Established)
  - not reported any more: lldp spine2:Ethernet1 -> leaf1:Ethernet2
  - not reported any more: lldp leaf1:Ethernet2 -> spine2:Ethernet1

  cabled            to               a_status  b_status
  spine2:Ethernet1  leaf1:Ethernet2  down      down

  device  peer    state   last_up
  leaf1   spine2  Active  2026-11-20T04:15:16Z
  spine2  leaf1   Active  2026-11-20T04:15:16Z
```
Both ends go down (the leaf's port loses carrier, not just the spine's admin state). `make break X=bgp` (leaf2
shuts its session to spine1): drift-links 0 rows; drift-bgp `leaf2 spine1 Idle` and `spine1 leaf2 Active`. So
the two queries separate a cabling fault from a routing one.

### 5.1

```cypher
MATCH (s:Service)-[:DEPENDS_ON]->(a:App)-[f:TALKS_TO]->(b:App),
      (a)-[:RUNS_ON]->(ha:Host), (b)-[:RUNS_ON]->(hb:Host)
WHERE NOT EXISTS {
  MATCH p = (ha)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(hb)
  WHERE none(n IN nodes(p) WHERE n:Device AND n.name = $device)
}
RETURN s.name AS service, s.tier AS tier, a.name + " -> " + b.name + " :" + f.port AS flow
ORDER BY tier, service, flow;

MATCH (x:Device)
MATCH (s:Service {tier: 1})-[:DEPENDS_ON]->(a:App)-[:TALKS_TO]->(b:App),
      (a)-[:RUNS_ON]->(ha:Host), (b)-[:RUNS_ON]->(hb:Host)
WHERE EXISTS { (ha)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(hb) }
  AND NOT EXISTS {
    MATCH p = (ha)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(hb)
    WHERE none(n IN nodes(p) WHERE n = x)
  }
RETURN x.name AS device, collect(DISTINCT s.name) AS breaks
ORDER BY device;
```
The `EXISTS` in spof.cypher matters: without it, a flow that's already broken makes every device look like its
single point of failure (found while building 5.2's overlap case). The walk uses the intent's CABLED_TO, so it
answers "what if" against the design, not the current state.

Blast radius, real:
| Device | Service, tier, flow |
|---|---|
| spine1 (and spine2) | nothing |
| leaf1 | Online orders, 1, web-shop -> orders-db :5432 |
| leaf2 | Network monitoring, 3, netmon -> web-shop :443 |
| leaf3 | Online orders, 1, web-shop -> payments :443 |
| leaf4 | Online orders, 1, web-shop -> orders-db :5432 · Online orders, 1, web-shop -> payments :443 · Network monitoring, 3, netmon -> web-shop :443 |

SPOFs for tier 1: leaf1, leaf3, leaf4, each `['Online orders']`. Spines: none. leaf2 isn't one (it only carries
tier 3). Without the spine2-leaf1 cable, spine1 joins the list.

### 5.2 (twin/whatif.py)

```cypher
MATCH (a:Interface)-[r:CABLED_TO]-(:Interface) WHERE a.id IN $ids DELETE r
MATCH (d:Device)-[:HAS_INTERFACE]->(:Interface)-[r:CABLED_TO]-(:Interface) WHERE d.name IN $devices DELETE r

MATCH (s:Service)-[:DEPENDS_ON]->(a:App)-[f:TALKS_TO]->(b:App),
      (a)-[:RUNS_ON]->(ha:Host), (b)-[:RUNS_ON]->(hb:Host)
WHERE NOT EXISTS { (ha)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(hb) }
RETURN s.name AS service, a.name + " -> " + b.name + " :" + f.port AS flow
ORDER BY service, flow
```
One explicit transaction (`session.begin_transaction()`): spof.cypher before, the deletes, broken-now, spof.cypher
after, then `tx.rollback()` in a `finally`. Real output:
```
  what if: lose the spine2-leaf1 link  (1 link removed, inside a transaction)
  ✓ broken now: nothing, every flow still has a path
  ! new single point of failure: spine1, for Online orders
  rolled back: the graph is as it was

  what if: drain spine1  (4 links removed, inside a transaction)
  ✓ broken now: nothing, every flow still has a path
  ! new single point of failure: spine2, for Online orders
  rolled back: the graph is as it was

  what if: drain spine1 while the spine2-leaf1 link is out  (5 links removed, inside a transaction)
  ✗ broken now: Online orders: web-shop -> orders-db :5432
  ! new single point of failure: spine2, for Online orders
  rolled back: the graph is as it was
```
The checker fingerprints the whole graph before and after all three: identical.

### 6.1 (twin/changes.py)

Python, not Cypher: it diffs the two newest snapshot folders on disk (sets of
`switch:port -> neighbor:port` strings; `{(switch, peer description): peerState}`). The graph holds only now; the
history is the snapshots. Real output across the link fault and back:
```
  changes from 2026-11-20T04:15:16Z to 2026-11-20T04:15:23Z:
  - lldp gone      leaf1:Ethernet2 -> spine2:Ethernet1
  - lldp gone      spine2:Ethernet1 -> leaf1:Ethernet2
  ~ bgp            leaf1 -> spine2: Established → Active
  ~ bgp            spine2 -> leaf1: Established → Active

  changes from 2026-11-20T04:15:23Z to 2026-11-20T04:15:34Z:
  + lldp appeared  leaf1:Ethernet2 -> spine2:Ethernet1
  + lldp appeared  spine2:Ethernet1 -> leaf1:Ethernet2
  ~ bgp            leaf1 -> spine2: Active → Established
  ~ bgp            spine2 -> leaf1: Active → Established
```
BGP and LLDP were both back within 10 s of `make fix`. A whole refresh (collect, load, diff) takes about a second.
The lab doesn't schedule refreshes; "keep it current" is `make refresh` run by hand, by the checker, or (in the
lesson, not the lab) on a timer or on an alert.

### 6.2 (twin/mcp_server.py)

```python
def read(text, params=None, limit=MAX_ROWS):          # MAX_ROWS = 100, TIMEOUT = 10
    @unit_of_work(timeout=TIMEOUT)
    def work(tx):
        result = tx.run(text, params or {})
        return [r.data() for r in result.fetch(limit)]
    try:
        with twin.driver() as d, d.session() as s:
            return s.execute_read(work)
    except Neo4jError as e:
        raise ToolError(e.message) from e
```
Tools: `blast_radius(device)` (runs queries/blast-radius.cypher), `path(src, dst)` (queries/path.cypher),
`cypher(query, params=None)`. FastMCP 4.2.2: `FastMCP("network-twin", instructions=...)`, `@mcp.tool`,
`mcp.run()` (stdio). Real calls from `lab/ask.py` (fastmcp's in-memory `Client(mcp)`):
```
  blast_radius(device='leaf1')
    {"service": "Online orders", "tier": 1, "flow": "web-shop -> orders-db :5432"}
  path(src='host1', dst='host2')
    {"hops": ["leaf1", "spine1", "leaf4"]}
  cypher(query="MATCH (d:Device {name: $name}) SET d.role = 'changed' RETURN d.name", params={'name': 'spine1'})
  ✗ error: Writing in read access mode not allowed. Attempted write to neo4j
```
The refusal is Neo4j's own, from the READ transaction, not a text filter. A runaway query
(`UNWIND range(1, 2000000000) ...`) was stopped after about 12 s with: "The transaction has not completed within
the timeout specified at its start by the client." `UNWIND range(1, 1000)` returns 100 rows. Note:
`neo4j.Query(text, timeout=...)` works only with `session.run`; in a transaction function the timeout goes on
`@unit_of_work`. Neo4j Community has no role-based access control, so read-only per transaction is what's
available; on Enterprise you'd also give the server a reader-only user.

## The whole lab, timed

`make check` on the solution: 12/12 tasks, 48 checks, 31 s (it breaks and fixes the fabric four times). Starting
from `main` with `make solve` for every task, then `make check`: 12/12. On `main` as shipped, every task fails
with its TODO named, for example `twin/load_intent.py: TODO 2.2a is still open`,
`queries/neighbors.cypher has no query in it yet`, `COMMANDS is empty: TODO 3.1a is still open`.

## Known gaps

- `make images` pulls the public CapeOS image anonymously (checked from the dev container's inner Docker, which has
  no registry credentials).
- Neo4j's browser in Codespaces: ports 7474 and 7687 are forwarded, but the browser page has to be given the
  forwarded bolt address. Not tested. Every task works without the browser (`make cypher`, `make shell`).
- `make solve T=5.2` from tag solution-ch5 has an older marker comment in whatif.py (code identical).
- Chapter 1's file empties the graph. The checker rebuilds chapter 2-3's graph afterwards; a learner re-running
  1.1 later needs `make load` and `make refresh` again (the guide says so).

Outputs for the guide pages come from `.maint/capture.sh` (run in the dev container on the solution branch;
writes build/capture/). The pages in the website repo were written from that run, by hand.
