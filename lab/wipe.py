"""make wipe · empty the graph: every node and relationship, then every constraint and index you made.

For starting a chapter over. Nothing on the switches changes, and build/snapshots/ stays where it is.
"""
import pathlib
import sys

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import twin  # noqa: E402

twin.wipe()
for r in twin.rows("SHOW CONSTRAINTS YIELD name"):
    twin.rows(f"DROP CONSTRAINT {r['name']}")
for r in twin.rows("SHOW INDEXES YIELD name, type, owningConstraint WHERE type <> 'LOOKUP' AND owningConstraint IS NULL"):
    twin.rows(f"DROP INDEX {r['name']}")
print("  the graph is empty: no nodes, relationships, constraints or indexes")
