// Task 2.1 · the graph's schema: what must be unique, and what to look things up by.
//   make cypher F=graph/schema.cypher
//
// A uniqueness constraint does two jobs: it refuses a second node with the same value, and it gives MERGE an index
// to find the first one fast. Neo4j Community edition has uniqueness constraints only (node keys and "must exist"
// constraints are Enterprise), so every kind of node gets one property that names it.
// IF NOT EXISTS makes every line safe to run again: the load in task 2.2 runs this file first, every time.
//
// TODO 2.1a  (follow along) Device by name, Interface by id ("leaf1:Ethernet1"), and an index on
//            Interface's device, for "every interface on leaf1".
// TODO 2.1b  (challenge) one uniqueness constraint each for Site, Subnet, Host, App and Service. Which property
//            names each one? The table in the guide says.
