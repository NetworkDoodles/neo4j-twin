// Task 4.2 · TODO 4.2a (follow along): cables the intent says are there, that LLDP doesn't see from both ends.
//   make cypher F=queries/drift-links.cypher
//
// Drift is a difference between the two sides of the twin. Here: a CABLED_TO between two interfaces with no
// LLDP_NEIGHBOR one way or the other. A pattern can be a test in a WHERE clause: NOT (a)-[:LLDP_NEIGHBOR]->(b) is
// true when there's no such relationship.
// Columns: cabled (a's id), to (b's id), a_status and b_status (each end's oper_status), sorted by cabled.
// A healthy fabric returns no rows.
