# Maintainers: real output for the guide pages, from a solution checkout with the lab up. Run inside the dev container:
#   bash .maint/capture.sh     (writes build/capture/*.txt; it breaks and fixes the fabric twice)
cd /workspaces/neo4j-twin
export VENV=/home/vscode/.venvs/lab NO_COLOR=1
P=$VENV/bin/python; Q="$P lab/cypher.py"
O=/workspaces/neo4j-twin/build/capture; mkdir -p $O
make -s wipe >/dev/null
$Q cypher/fabric.cypher > $O/1.1.txt
$Q queries/neighbors.cypher device=leaf1 > $O/1.2a.txt; $Q queries/links-per-device.cypher > $O/1.2b.txt
$Q queries/neighbors.cypher device=spine2 > $O/1.2c.txt
$Q graph/schema.cypher > $O/2.1.txt; $Q lab/show-schema.cypher > $O/2.1-show.txt; $Q graph/schema.cypher > $O/2.1-again.txt
$P twin/load_intent.py > $O/2.2.txt; $P twin/load_intent.py > $O/2.2-again.txt
$Q /dev/stdin > $O/2.2-q.txt <<'Q'
MATCH (s:Service {name: "Online orders"})-[:DEPENDS_ON]->(a:App)-[:RUNS_ON]->(h:Host)-[:ATTACHED_TO]->(i:Interface)<-[:HAS_INTERFACE]-(d:Device) RETURN s.name AS service, a.name AS app, h.name AS host, i.id AS port ORDER BY app;
Q
$P twin/collect.py > $O/3.1.txt; ls build/snapshots | tail -1 > $O/3.1-ls.txt
S=$(ls -d build/snapshots/*/ | tail -1); head -c 900 $S/leaf1.json > $O/3.1-leaf1.txt; cat $S/meta.json > $O/3.1-meta.txt
curl -sk -u admin:capeos-lab https://172.80.91.21/command-api -d '{"jsonrpc":"2.0","method":"runCmds","params":{"version":1,"cmds":["show lldp neighbors"],"format":"json"},"id":1}' > $O/3.1-curl.txt
$P twin/load_state.py > $O/3.2.txt
$Q /dev/stdin > $O/3.2-q.txt <<'Q'
MATCH (a:Interface {id: "leaf1:Ethernet1"})-[c:CABLED_TO|LLDP_NEIGHBOR]-(b:Interface) RETURN type(c) AS rel, startNode(c).id AS from, endNode(c).id AS to;
MATCH (:Device {name: "leaf1"})-[r:BGP_PEER]->(p:Device) RETURN p.name AS peer, r.state AS state, r.prefixes AS prefixes, r.seen_at AS seen_at, r.last_seen AS last_seen ORDER BY peer;
Q
$Q queries/path.cypher from=host1 to=host2 > $O/4.1a.txt; $Q queries/ecmp.cypher from=host1 to=host2 > $O/4.1b.txt
$Q queries/drift-links.cypher > $O/4.2-healthy-links.txt; $Q queries/drift-bgp.cypher > $O/4.2-healthy-bgp.txt
$P lab/faults.py link > $O/4.2-break.txt; sleep 5; $P twin/collect.py >/dev/null; $P twin/load_state.py > $O/4.2-load.txt
$Q queries/drift-links.cypher > $O/4.2-links.txt; $Q queries/drift-bgp.cypher > $O/4.2-bgp.txt
$P twin/changes.py > $O/6.1-broken.txt
$P lab/faults.py fix > $O/4.2-fix.txt; sleep 10; $P twin/collect.py >/dev/null; $P twin/load_state.py > $O/4.2-load2.txt; $P twin/changes.py > $O/6.1-fixed.txt
$P lab/faults.py bgp > /dev/null; sleep 5; $P twin/collect.py >/dev/null; $P twin/load_state.py >/dev/null
$Q queries/drift-links.cypher > $O/4.2-bgpfault-links.txt; $Q queries/drift-bgp.cypher > $O/4.2-bgpfault-bgp.txt
$P lab/faults.py fix >/dev/null; sleep 10; $P twin/collect.py >/dev/null; $P twin/load_state.py >/dev/null
for d in leaf1 spine1 leaf4 leaf3 leaf2; do $Q queries/blast-radius.cypher device=$d > $O/5.1-$d.txt; done
$Q queries/spof.cypher > $O/5.1-spof.txt
for c in lose-spine2-leaf1 drain-spine1 maintenance-overlap; do $P twin/whatif.py changes/$c.yml > $O/5.2-$c.txt; done
$P twin/collect.py > /dev/null; $P twin/load_state.py > /dev/null; $P twin/changes.py > $O/6.1-healthy.txt
$P lab/ask.py > $O/6.2.txt 2>&1
for t in 1.1 1.2 2.1 2.2 3.1 3.2 4.1 4.2 5.1 5.2 6.1 6.2; do $P checks/check.py $t > $O/check-$t.txt 2>&1; done
time (for i in 1 2 3 4 5; do $P twin/collect.py; done) > $O/3.1-timings.txt 2>&1
