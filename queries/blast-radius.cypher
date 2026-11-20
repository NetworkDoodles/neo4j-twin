// Task 5.1 · TODO 5.1a (follow along): if $device fails, which business services lose a flow, and which flows?
//   make cypher F=queries/blast-radius.cypher P='device=leaf1'
//
// Walk up from the network to the business: Service -[:DEPENDS_ON]-> App -[:TALKS_TO]-> App, each App RUNS_ON a
// Host. A flow is broken by $device if every path between its two hosts goes through $device: in Cypher, there
// is NOT EXISTS a path (the same three relationship types as task 4.1) where none() of the nodes is that device.
// Columns: service, tier, flow ("web-shop -> orders-db :5432"), sorted by tier, service, flow.
