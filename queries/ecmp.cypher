// Task 4.1 · TODO 4.1b (challenge): how many equal-cost paths are there between two hosts, and through which spines?
//   make cypher F=queries/ecmp.cypher P='from=host1 to=host2'
//
// shortestPath() returns one path. allShortestPaths() returns every path of that same shortest length: in a
// spine/leaf fabric, one per spine, which is ECMP (equal-cost multipath) seen from the cabling.
// Return two columns: paths (how many) and via (the spine each one goes through, in order: ORDER BY before
// collect() sorts the list).
// >>> solution
MATCH (a:Host {name: $from}), (b:Host {name: $to})
MATCH p = allShortestPaths((a)-[:ATTACHED_TO|HAS_INTERFACE|CABLED_TO*]-(b))
WITH p, [n IN nodes(p) WHERE n:Device AND n.role = "spine" | n.name][0] AS spine
ORDER BY spine
RETURN count(p) AS paths, collect(spine) AS via;
// <<< solution
