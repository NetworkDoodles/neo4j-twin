# The lab's dev container: containerlab's Docker-in-Docker image plus the lab's Python tools.
# The venv is built here, in the image, so the Neo4j driver is on PATH from the first second, before any terminal
# opens or any extension looks for it.
FROM ghcr.io/srl-labs/containerlab/devcontainer-dind-slim:0.82.0

USER vscode
ENV VENV=/home/vscode/.venvs/lab
ENV PATH=/home/vscode/.venvs/lab/bin:$PATH
COPY --chown=vscode:vscode requirements.txt /tmp/lab/
# .ok records which requirements were installed (the same hash `make setup` checks), so the first start
# doesn't reinstall them.
RUN uv venv -q --python 3.13 "$VENV" \
 && uv pip install -q --python "$VENV/bin/python" -r /tmp/lab/requirements.txt \
 && cd /tmp/lab && python3 -c "import hashlib,sys; print(hashlib.sha256(b''.join(open(f,'rb').read() for f in sys.argv[1:])).hexdigest()[:16])" requirements.txt > "$VENV/.ok"

# code-server reads its own settings, not devcontainer.json's: the workspace's .vscode/ covers the
# extensions, and these user settings cover what a workspace isn't allowed to set.
COPY --chown=vscode:vscode .devcontainer/code-server-settings.json /home/vscode/.local/share/code-server/User/settings.json
