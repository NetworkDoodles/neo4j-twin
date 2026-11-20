// Task 1.2 · TODO 1.2b (challenge): every device, its role, and how many links it has.
//   make cypher F=queries/links-per-device.cypher
// Columns: device, role, links. Most links first, then by name.
// >>> solution
MATCH (d:Device)-[l:LINK]-()
RETURN d.name AS device, d.role AS role, count(l) AS links
ORDER BY links DESC, device;
// <<< solution
