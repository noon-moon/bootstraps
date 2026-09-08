# Base: node 22 bookworm-slim (glibc) — backlog.md ships a glibc binary and
# musl (alpine) fails with ENOENT; opencode-ai linux-arm64 tarball is likewise
# glibc-linked. Digest-pinned to the immutable manifest digest (per-arch
# digests recorded in docs/private-access.md).
FROM node@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

# Build-time installs only: services never apt/npm/curl on restart.
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user; HOME carries opencode session state (auth.json, db).
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 agent

# Pinning: OPENCODE_VERSION is the release tag; BACKLOG_VERSION is the npm
# version of backlog.md. npm package integrity SHAs are recorded in
# docs/private-access.md (registry content-addressed, not mutable tags).
ARG OPENCODE_VERSION=1.18.29
ARG BACKLOG_VERSION=1.51.0

# backlog.md 1.51.0 (glibc linux-arm64/x64 native binary via npm optionalDeps)
RUN npm install --global backlog.md@"${BACKLOG_VERSION}" \
    && npm cache clean --force \
    && backlog --version

# opencode-ai 1.18.29 via npm — the SELECTED distribution for this pinned
# version. (An official ghcr.io/anomalyco/opencode image exists but its tag
# set does not include 1.18.29; see docs/private-access.md for the recorded
# digests and distribution decision.) npm resolves the platform-specific
# optionalDependency (opencode-linux-arm64/x64[-musl]).
RUN npm install --global opencode-ai@"${OPENCODE_VERSION}" \
    && npm cache clean --force \
    && opencode --version \
    && chown -R agent:agent /home/agent

# Config lives in a named volume mounted at /home/agent/.config/opencode
# (compose runs deploy/scripts/seed-opencode-config.sh at first boot: it
# writes opencode.json with a local Backlog MCP pointed at the same
# BACKLOG_CWD as the ledger service — one authoritative resource, no phantom
# isolated ledger). Sessions live in a separate named volume.
# Volume mountpoints are pre-created with agent ownership so the named
# volumes (created root-owned by default) are usable by the non-root uid.
ENV HOME=/home/agent
ENV XDG_CONFIG_HOME=/home/agent/.config
ENV XDG_DATA_HOME=/home/agent/.local/share
ENV OPENCODE_CONFIG=/home/agent/.config/opencode/opencode.json

RUN mkdir -p /home/agent/.config/opencode \
             /home/agent/.local/share/opencode \
             /home/agent/.local/state \
             /workspace /data \
    && chown -R agent:agent /home/agent/.config /home/agent/.local /workspace /data

USER agent
WORKDIR /workspace