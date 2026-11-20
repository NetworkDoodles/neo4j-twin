"""Render each switch's factory config from fabric/intent.yml into build/startup/ (make up runs this).

The switches boot from these copies, so whatever you change on a switch never touches a file Git tracks.
`make reset` renders them again and restarts the fabric.
"""
import pathlib
import sys

import jinja2

sys.path.insert(0, pathlib.Path(__file__).resolve().parents[1].as_posix())
from lib import fabric  # noqa: E402

OUT = fabric.ROOT / "build" / "startup"


def render(intent=None):
    intent = intent or fabric.load()
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(fabric.ROOT / "lab" / "templates"),
                             trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)
    tpl = env.get_template("startup.cfg.j2")
    ports = fabric.interfaces(intent)
    peer_asn = {n: fabric.asn(intent, n) for n in intent["devices"]}
    out = {}
    for name, dev in intent["devices"].items():
        out[name] = tpl.render(name=name, dev=dev, ports=ports[name], asn=fabric.asn(intent, name),
                               peer_asn=peer_asn, mtu=intent["fabric"]["mtu"])
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in render().items():
        (OUT / f"{name}.cfg").write_text(text)
    print(f"  rendered {len(fabric.switches())} startup configs into build/startup/")
