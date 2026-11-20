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
// >>> solution
CREATE CONSTRAINT device_name IF NOT EXISTS FOR (d:Device) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT interface_id IF NOT EXISTS FOR (i:Interface) REQUIRE i.id IS UNIQUE;
CREATE INDEX interface_device IF NOT EXISTS FOR (i:Interface) ON (i.device);
// <<< solution
// >>> solution
CREATE CONSTRAINT site_name IF NOT EXISTS FOR (s:Site) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT subnet_prefix IF NOT EXISTS FOR (s:Subnet) REQUIRE s.prefix IS UNIQUE;
CREATE CONSTRAINT host_name IF NOT EXISTS FOR (h:Host) REQUIRE h.name IS UNIQUE;
CREATE CONSTRAINT app_name IF NOT EXISTS FOR (a:App) REQUIRE a.name IS UNIQUE;
CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;
// <<< solution
