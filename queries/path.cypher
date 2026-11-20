// Task 4.1 · TODO 4.1a (follow along): the devices on the shortest path between two hosts.
//   make cypher F=queries/path.cypher P='from=host1 to=host2'
//
// A path through the physical twin goes host -[:ATTACHED_TO]-> leaf port <-[:HAS_INTERFACE]- leaf -[:HAS_INTERFACE]->
// uplink -[:CABLED_TO]- spine port ... and so on. Let Cypher find it: shortestPath() over a variable-length pattern
// of just those three relationship types, in either direction (no arrowhead), between the two Host nodes.
// Return one column, hops: the names of the Devices on the path, in order. nodes(p) is every node on the path;
// a list comprehension [n IN nodes(p) WHERE n:Device | n.name] keeps the devices' names.
// >>> solution
MATCH (a:Host {name: $from}), (b:Host {name: $to})
MATCH p = shortestPath((a)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(b))
RETURN [n IN nodes(p) WHERE n:Device | n.name] AS hops;
// <<< solution
