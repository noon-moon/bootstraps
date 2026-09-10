# Base: node 22 bookworm-slim (glibc) — backlog.md ships a glibc binary;
# musl (alpine) fails with ENOENT. Digest-pinned to the immutable manifest
# digest (per-arch digests recorded in docs/private-access.md).
FROM node@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user; uid 10001 matches the opencode image so shared
# volume ownership rules stay simple.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 agent

ARG BACKLOG_VERSION=1.51.0

# Build-time install (never npm on restart). The browser subcommand binds
# 127.0.0.1 inside THIS container's network namespace (hardcoded; no --host
# flag in 1.51.0) — exposure is via the relay service sharing this netns.
RUN npm install --global backlog.md@"${BACKLOG_VERSION}" \
    && npm cache clean --force \
    && backlog --version

ENV HOME=/home/agent
ENV BACKLOG_CWD=/data
ENV XDG_CONFIG_HOME=/home/agent/.config

# /data is the authoritative Backlog resource mount (fixture here; the
# external private context repo supplies the real ledger on the droplet).
# Pre-created with agent ownership so a named/root-created mount target is
# usable by the non-root uid. NOTE: bind-mount ownership is NOT chowned at
# runtime — the fixture/ledger directory must already be writable by uid
# 10001 (the smoke harness ensures this for its fixture; operators supply
# a prepared resource).
RUN mkdir -p /data /home/agent/.config /home/agent/.local/state \
    && chown -R agent:agent /data /home/agent

USER agent
WORKDIR /data