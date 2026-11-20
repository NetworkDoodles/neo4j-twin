// The schema as Neo4j has it now: your constraints and indexes (make run T=2.1 runs this after yours)
SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties RETURN name, labelsOrTypes, properties ORDER BY name;
SHOW INDEXES YIELD name, labelsOrTypes, properties, type, owningConstraint
  WHERE type <> "LOOKUP" AND owningConstraint IS NULL
  RETURN name, labelsOrTypes, properties ORDER BY name;
