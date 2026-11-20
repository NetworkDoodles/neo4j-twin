# neo4j-twin: facts for the lessons

Everything here comes from the lab's own files and from real runs. Sections marked (pending) are filled in as the
lab is built and run.

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
