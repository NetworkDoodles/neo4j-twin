"""make cypher F=<file> [P='name=value ...']  ·  run a .cypher file against the graph and print what it returns.

A file can hold several statements, each ending in `;`. Parameters ($device, $from ...) come from P:
    make cypher F=queries/blast-radius.cypher P='device=leaf1'
Values that look like numbers are passed as numbers. Lines starting with // are comments.

For poking around, `make shell` opens cypher-shell, Neo4j's own command line, and http://localhost:7474 draws
the graph.
"""
import pathlib
import sys

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import twin  # noqa: E402


def statements(text):
    lines = [l for l in text.splitlines() if not l.strip().startswith("//")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def value(v):
    try:
        return int(v)
    except ValueError:
        return v


def params(args):
    out = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            out[k] = value(v)
    return out


def show(records, keys):
    if not keys:
        return
    cells = [[str(r.get(k)) if not isinstance(r.get(k), str) else r.get(k) for k in keys] for r in records]
    width = [max([len(k)] + [len(c[i]) for c in cells]) for i, k in enumerate(keys)]
    print("  " + "  ".join(k.ljust(w) for k, w in zip(keys, width)))
    print("  " + "  ".join("─" * w for w in width))
    for c in cells:
        print("  " + "  ".join(x.ljust(w) for x, w in zip(c, width)))
    print(f"  ({len(records)} row{'s' if len(records) != 1 else ''})")


ORDER = ["nodes_created", "nodes_deleted", "relationships_created", "relationships_deleted", "properties_set",
         "labels_added", "constraints_added", "constraints_removed", "indexes_added", "indexes_removed"]


def changed(c):
    done = [(k, getattr(c, k, 0)) for k in ORDER if getattr(c, k, 0)]
    return ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in done) or "done, nothing changed"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: make cypher F=<file.cypher> [P='name=value ...']")
    path = pathlib.Path(sys.argv[1])
    p = params(" ".join(sys.argv[2:]).split())
    from neo4j.exceptions import Neo4jError
    with twin.driver() as d:
        for stmt in statements(path.read_text()):
            try:
                records, summary, keys = d.execute_query(stmt, p)
            except Neo4jError as e:
                sys.exit(f"  ✗ {path}: {e.message}")
            if keys:
                show([r.data() for r in records], keys)
            else:
                print("  " + changed(summary.counters))


if __name__ == "__main__":
    main()
