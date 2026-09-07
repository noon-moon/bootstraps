## Purpose

Defines Tailscale-private exposure of the OpenCode server and Backlog browser to
the user's phone and laptop: listener policy, proxy mechanics, auth, ACL scope,
and the public-exposure prohibition.

## ADDED Requirements

### Requirement: Private exposure over the existing tailnet
OpenCode server and Backlog browser SHALL be reachable from the user's tailnet
devices (phone, laptop) and from nothing else. Tailscale on the droplet SHALL
join the existing tailnet; tailnet ACLs SHALL restrict the new node to the
user's devices; Tailscale SSH MAY replace password/interactive SSH for
administration. Public exposure (Funnel, public DNS, the site's Caddy) is
prohibited for these services.

#### Scenario: Phone reaches Backlog over Tailscale
- **WHEN** the user opens the Backlog browser URL from their phone on the
  tailnet
- **THEN** the UI loads and supports task creation/comments/ordering over the
  private overlay

#### Scenario: Public interface reaches nothing new
- **WHEN** a request arrives from the public internet to the droplet's public
  address for OpenCode/Backlog ports
- **THEN** it is refused (no public listener); the public site's Caddy on
  noonmoon is unrelated and untouched

### Requirement: Proxy mechanics verified, not assumed
Where a proxy is needed (e.g., Backlog's loopback-bound browser served over
Tailscale), the mechanism SHALL be Tailscale Serve or an equivalent private
proxy, validated for: correct Origin/Host handling, WebSocket support (Backlog's
live updates), and no TLS/certificate breakage on iOS clients. A proxy
configuration that fails any of these SHALL be reported and not deployed.

#### Scenario: WebSocket updates work through the proxy
- **WHEN** the Backlog UI is open via the private proxy
- **THEN** live-update events (WebSocket) reach the client without errors

#### Scenario: Origin validation does not break iOS
- **WHEN** the phone accesses the proxied UI
- **THEN** origin/Host checks pass for the tailnet hostname and no cert warning
  blocks the UI

### Requirement: Credential policy for services
Service credentials (OpenCode basic auth, deploy keys, model API keys) SHALL be
provisioned via the context repo's credential references resolved at service
start; secrets SHALL NOT be committed to bootstraps or baked into public
images. The OpenCode server password SHALL be unique per service and treated as
transport security only — it is not role-based authorization.

#### Scenario: Credentials come from context
- **WHEN** the compose stack starts on the droplet
- **THEN** secrets resolve from context references (env/file), and no secret
  value appears in bootstraps, the run log, or the compose file in the public
  repo

### Requirement: Model/provider disclosure is explicit
Cloud model inference from the VPS SHALL use explicitly configured providers
and models recorded in context; private vault material SHALL NOT be sent to
cloud models during MVP (personal vault work stays laptop-local; VPS serves
non-private project work). Any change to which content may reach which provider
is a separate authorization decision (V2 local-only processing is TASK-44.8).

#### Scenario: Default VPS scope excludes private vault content
- **WHEN** a VPS-side agent session processes project work
- **THEN** only explicitly authorized (non-private-scope) resources are read;
  private vault content is not in the VPS working set during MVP