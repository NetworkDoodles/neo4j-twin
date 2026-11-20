# Network Doodles lab · Graph digital twins with Neo4j
# Guide: https://networkdoodles.com/labs/neo4j-twin/
#
# Tasks are numbered chapter.task, so T=2.1 is chapter 2, task 1. CH=<n> means a whole chapter.
.DEFAULT_GOAL := help
# The dev container keeps its venv outside the repo (VENV is set there); locally it is .venv.
VENV ?= .venv
PY := $(VENV)/bin/python
BIN := $(VENV)/bin
GUIDE := https://networkdoodles.com/labs/neo4j-twin
TOPO := lab/topology.clab.yml
PULSE := ghcr.io/dkhenderson2/capeos-pulse:0.11.2
NEO4J := neo4j:5.26.32-community
T ?=
CH ?=
F ?=
P ?=
C ?=
X ?=
CYPHER = $(PY) lab/cypher.py

# What `make run T=<id>` runs: the command the guide has you type, for when you just want to see it.
RUN_1.1 := $(CYPHER) cypher/fabric.cypher
RUN_1.2 := $(CYPHER) queries/neighbors.cypher device=leaf1 && $(CYPHER) queries/links-per-device.cypher
RUN_2.1 := $(CYPHER) graph/schema.cypher && $(CYPHER) lab/show-schema.cypher
RUN_2.2 := $(CYPHER) graph/schema.cypher >/dev/null && $(PY) twin/load_intent.py
RUN_3.1 := $(PY) twin/collect.py
RUN_3.2 := $(PY) twin/load_state.py
RUN_4.1 := $(CYPHER) queries/path.cypher from=host1 to=host2 && $(CYPHER) queries/ecmp.cypher from=host1 to=host2
RUN_4.2 := $(CYPHER) queries/drift-links.cypher && $(CYPHER) queries/drift-bgp.cypher
RUN_5.1 := $(CYPHER) queries/blast-radius.cypher device=leaf1 && $(CYPHER) queries/spof.cypher
RUN_5.2 := $(PY) twin/whatif.py changes/lose-spine2-leaf1.yml
RUN_6.1 := $(PY) twin/collect.py && $(PY) twin/load_state.py && $(PY) twin/changes.py
RUN_6.2 := $(PY) lab/ask.py

help: ## show this help
	@grep -hE '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# The venv's .ok holds a hash of the requirements it was built from (the dev container's image writes the
# same hash), so a fresh checkout doesn't reinstall a venv that's already right.
REQS := requirements.txt
REQ_HASH = $(shell python3 -c "import hashlib,sys; print(hashlib.sha256(b''.join(open(f,'rb').read() for f in sys.argv[1:])).hexdigest()[:16])" $(REQS))

setup: ## create the Python venv with the Neo4j driver and the lab's tools
	@if [ "$$(cat $(VENV)/.ok 2>/dev/null)" = "$(REQ_HASH)" ] && [ -x $(PY) ]; then exit 0; fi; \
	echo "installing the lab's Python tools into $(VENV)"; \
	if command -v uv >/dev/null; then \
	  uv venv -q --allow-existing --python 3.13 $(VENV) && uv pip install -q --python $(PY) -r requirements.txt; \
	else \
	  python3 -m venv $(VENV) && $(PY) -m pip install -q --upgrade pip && $(PY) -m pip install -q -r requirements.txt; \
	fi && echo "$(REQ_HASH)" > $(VENV)/.ok

# The dev container's own Docker engine starts alongside the container, so the first commands can beat it.
docker-ready:
	@for i in $$(seq 1 60); do docker info >/dev/null 2>&1 && exit 0; [ $$i = 1 ] && echo "  waiting for Docker to start ..."; sleep 2; done; \
	echo "Docker isn't answering. In the dev container it starts on its own; on a laptop, start Docker Desktop."; exit 1

images: docker-ready ## pull the switch, host and Neo4j images (the dev container does this once)
	@for i in $(PULSE) alpine:3.22 $(NEO4J); do docker pull -q $$i & done; wait

up: setup docker-ready ## start the fabric (six switches, four hosts) and Neo4j: about two minutes
	@command -v containerlab >/dev/null || (echo "containerlab isn't installed: it comes with the dev container"; exit 2)
	@docker image inspect $(PULSE) >/dev/null 2>&1 || $(MAKE) images
	@# The switches boot from configs rendered from fabric/intent.yml into build/startup/.
	@$(PY) lab/render.py
	containerlab deploy -t $(TOPO) --reconfigure
	docker compose up -d
	@$(PY) lab/faults.py forget
	@$(PY) lab/wait.py

down: ## remove the fabric and stop Neo4j (the graph is kept)
	containerlab destroy -t $(TOPO) --cleanup
	docker compose stop

reset: ## every switch back to its factory config (your files and the graph are untouched)
	$(MAKE) up

wipe: ## empty the graph: every node and relationship, every constraint and index
	@$(PY) lab/wipe.py

ssh: ## open a switch's CLI:  make ssh NODE=leaf1
	@test -n "$(NODE)" || (echo "usage: make ssh NODE=leaf1  (spine1 spine2 leaf1 .. leaf4)"; exit 2)
	@docker exec -it $(NODE) capeos-cli

shell: ## open cypher-shell, Neo4j's own command line (:exit leaves it)
	@docker exec -it neo4j cypher-shell -u neo4j -p lab-twin-graph

cypher: ## run a .cypher file:  make cypher F=queries/blast-radius.cypher P='device=leaf1'
	@test -n "$(F)" || (echo "usage: make cypher F=<file.cypher> [P='name=value ...']"; exit 2)
	@$(CYPHER) $(F) $(P)

load: ## chapter 2: the schema, then the intent and the services, into the graph
	@$(CYPHER) graph/schema.cypher >/dev/null && $(PY) twin/load_intent.py

collect: ## chapter 3: read the switches' state into a snapshot in build/snapshots/
	@$(PY) twin/collect.py

refresh: ## chapters 3 and 6: collect, load the snapshot into the graph, then say what changed
	@$(PY) twin/collect.py && $(PY) twin/load_state.py && $(PY) twin/changes.py

whatif: ## chapter 5: try a change in the graph and roll it back:  make whatif C=lose-spine2-leaf1
	@test -n "$(C)" || (echo "usage: make whatif C=<change>   the changes are in changes/"; exit 2)
	@$(PY) twin/whatif.py changes/$(C).yml

mcp: ## chapter 6: run the read-only MCP server on stdio (an MCP client starts this for you)
	@$(PY) twin/mcp_server.py

break: ## break the fabric on purpose:  make break X=link  (link bgp)
	@test -n "$(X)" || (echo "usage: make break X=<link|bgp>"; exit 2)
	@$(PY) lab/faults.py $(X)

fix: ## undo everything make break did
	@$(PY) lab/faults.py fix

status: ## what's installed, what's running, and where to start  (WAIT=1 waits for the fabric)
	@$(PY) lab/status.py $(if $(WAIT),--wait)

run: ## run a task's command:  make run T=2.1
	@test -n "$(T)" || (echo "usage: make run T=<chapter.task>, e.g. T=2.1"; exit 2)
	$(RUN_$(T))

check: ## verify a task, a chapter or everything:  make check T=2.1 · CH=2 · (nothing)
	@$(PY) checks/check.py $(if $(T),$(T),$(if $(CH),ch$(CH),all))

# The answers: a tag at the end of every chapter on the solution branch (solution-ch1 ... solution-ch6).
solve: ## stuck? copy one task's finished files from the solution:  make solve T=2.1
	@test -n "$(T)" || (echo "usage: make solve T=<chapter.task>"; exit 2)
	@files=$$($(PY) checks/check.py --files $(T)); test -n "$$files" || { echo "task $(T) has no files to solve"; exit 2; }; \
	git fetch -q origin --tags 2>/dev/null || true; tag=solution-ch$$(echo $(T) | cut -d. -f1); \
	git checkout $$tag -- $$files && git reset -q -- $$files && echo "restored $$files from $$tag. Read what changed: git diff"

skip: ## start at any chapter: copy the finished files of every chapter before it  make skip CH=4
	@test -n "$(CH)" || (echo "usage: make skip CH=<chapter 2-6>"; exit 2)
	@files=$$($(PY) checks/check.py --files-before $(CH)); \
	git fetch -q origin --tags 2>/dev/null || true; tag=solution-ch$$(( $(CH) - 1 )); \
	git checkout $$tag -- $$files && git reset -q -- $$files && echo "copied the finished files of chapters 1 to $$(( $(CH) - 1 ))"

.PHONY: help setup docker-ready images up down reset wipe ssh shell cypher load collect refresh whatif mcp break fix status run check solve skip
