// Task 4.2 · TODO 4.2b (challenge): BGP sessions the design implies that aren't Established.
//   make cypher F=queries/drift-bgp.cypher
//
// The intent has no list of BGP sessions: the design says every cabled pair of switches peers. So the expected
// sessions are a pattern too: two Devices whose interfaces are CABLED_TO each other (either direction).
// For each, look for the device's own BGP_PEER to the other with OPTIONAL MATCH (a missing one is null, not a
// missing row), and keep the ones that are missing or not "Established".
// Columns: device, peer, state ("missing" when there's no BGP_PEER: coalesce() helps), last_up (its last_seen),
// sorted by device, then peer. A healthy fabric returns no rows.
