"""The fabric's intent (fabric/intent.yml), read into the shapes the lab's tools need.

Lab infrastructure: the startup configs, the checker and the chapter 2 loader read the fabric through here.
"""
import ipaddress
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTENT = ROOT / "fabric" / "intent.yml"


def load(path=INTENT):
    return yaml.safe_load(pathlib.Path(path).read_text())


def interfaces(intent=None):
    """{device: {port: {"address": "10.0.11.0/31", "peer": "leaf1", "peer_port": "Ethernet1", "peer_ip": ...}}}"""
    intent = intent or load()
    out = {name: {} for name in intent["devices"]}
    for link in intent["links"]:
        a_dev, a_port = link["a"].split(":")
        b_dev, b_port = link["b"].split(":")
        net = ipaddress.ip_network(link["subnet"])
        a_ip, b_ip = str(net[0]), str(net[1])
        out[a_dev][a_port] = {"address": f"{a_ip}/{net.prefixlen}", "ip": a_ip, "peer": b_dev, "peer_port": b_port, "peer_ip": b_ip}
        out[b_dev][b_port] = {"address": f"{b_ip}/{net.prefixlen}", "ip": b_ip, "peer": a_dev, "peer_port": a_port, "peer_ip": a_ip}
    return out


def asn(intent, name):
    d = intent["devices"][name]
    return d.get("asn") or intent["fabric"]["spine_asn"]


def switches(intent=None):
    intent = intent or load()
    return list(intent["devices"])


def mgmt(intent=None):
    intent = intent or load()
    return {name: d["mgmt"] for name, d in intent["devices"].items()}
