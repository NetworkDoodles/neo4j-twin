// Task 1.1 · the fabric, drawn by hand. Run it with:  make cypher F=cypher/fabric.cypher
//
// Every run starts from an empty graph (the first line), so you can run it as often as you like.
// A node is (name:Label {property: value}); a relationship is -[:TYPE]-> between two nodes you've named.
// Each new item starts with a comma. Names like spine1 below only last until the end of this one CREATE statement.
//
// TODO 1.1a  (follow along) spine2 and leaf1, and leaf1's two links, one to each spine.
// TODO 1.1b  (challenge) leaf2, leaf3 and leaf4, and their six links. fabric/intent.yml has their AS numbers.
MATCH (n) DETACH DELETE n;

CREATE
    (spine1:Device {name: "spine1", role: "spine", asn: 65000})
;
