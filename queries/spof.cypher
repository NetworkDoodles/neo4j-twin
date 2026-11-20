// Task 5.1 · TODO 5.1b (challenge): every single point of failure for a tier 1 service.
//   make cypher F=queries/spof.cypher
//
// The same question as blast-radius.cypher, asked of every device at once: MATCH every Device as x, and keep
// the tier 1 flows that have a path (EXISTS, no conditions) but no path avoiding x. Without the first part, a flow
// that's already broken would make every device look like its single point of failure. Task 5.2 runs this file inside a what-if, so keep it free of
// parameters.
// Columns: device, breaks (the tier 1 services it breaks, a list, no repeats), sorted by device.
