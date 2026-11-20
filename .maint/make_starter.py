#!/usr/bin/env python3
"""Maintainers only: turn the solution files into the starter files learners get on main.

Solution code sits between marker lines:

    # >>> solution | <optional starter line>        (Python and YAML)
    ...finished code...
    # <<< solution

    // >>> solution | <optional starter line>       (Cypher)
    // <<< solution

On main, each block becomes the starter line if one is given, otherwise
`raise NotImplementedError("TODO x.ya is still open")` for Python, or nothing for YAML and Cypher.

    python .maint/make_starter.py <solution checkout> <starter checkout>
"""
import re
import sys
import pathlib

FILES = [
    "cypher/fabric.cypher", "queries/neighbors.cypher", "queries/links-per-device.cypher", "graph/schema.cypher",
    "twin/load_intent.py", "twin/collect.py", "twin/load_state.py", "queries/path.cypher", "queries/ecmp.cypher",
    "queries/drift-links.cypher", "queries/drift-bgp.cypher", "queries/blast-radius.cypher", "queries/spof.cypher",
    "twin/whatif.py", "twin/changes.py", "twin/mcp_server.py",
]
REMOVE = []
OPEN = re.compile(r"^(\s*)(?:#|//) >>> solution(?: \| (.*))?$")
CLOSE = re.compile(r"^\s*(?:#|//) <<< solution$")


def strip(text, python):
    out, todo, skipping = [], "TODO", False
    for line in text.splitlines():
        if m := re.search(r"(TODO \d+\.\d+[a-z]?)", line):
            todo = m.group(1)
        if skipping:
            skipping = not CLOSE.match(line)
            continue
        if m := OPEN.match(line):
            indent, starter = m.groups()
            if starter:
                out.append(indent + starter)
            elif python:
                out.append(f'{indent}raise NotImplementedError("{todo} is still open")')
            skipping = True
            continue
        out.append(line)
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    src, dst = (pathlib.Path(p) for p in sys.argv[1:3])
    for f in FILES:
        source = src / f
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        (dst / f).write_text(strip(source.read_text(), f.endswith(".py")))
        print("starter:", f)
    for f in REMOVE:
        (dst / f).unlink(missing_ok=True)
        print("removed:", f)
