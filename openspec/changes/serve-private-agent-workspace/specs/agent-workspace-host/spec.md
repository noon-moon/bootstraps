## Purpose

Defines greenfield droplet provisioning as a bootstraps deployment: cloud-init
seed, headless bootstrap run, service lifecycle under Compose/systemd, capacity
measurement, and the cost/authorization gates.

## ADDED Requirements

### Requirement: Greenfield provisioning via bootstraps
The agent droplet SHALL be provisioned as a plain Ubuntu 24.04 droplet whose
first-boot cloud-init: creates the runtime user, installs the deploy SSH key,
clones bootstraps and the private context repo, and runs bootstrap in headless
mode with the headless-server profile. The deployment SHALL be reproducible
from (bootstraps revision + context revision + cloud-init seed) and its run log
SHALL be retrievable over SSH. No prebuilt machine image is required.

#### Scenario: Fresh droplet converges on first boot
- **WHEN** a new droplet boots with the cloud-init seed
- **THEN** bootstrap runs headless to completion, installs selected components
  (Docker, Tailscale, OpenCode, Backlog), and the full run log is readable over
  SSH for diagnosis

#### Scenario: Bootstrap failure is diagnosable remotely
- **WHEN** headless bootstrap exits non-zero on first boot
- **THEN** the exit code and log identify the failing component without
  requiring interactive access

### Requirement: Services run under Compose with private listeners
OpenCode server and Backlog browser SHALL run as Docker Compose services with
restart policies, on the host or loopback/Tailscale interfaces only. OpenCode
server SHALL require basic auth (`OPENCODE_SERVER_PASSWORD`). Backlog's browser
SHALL remain loopback-bound on the host with exposure handled by the private
access layer. No service in this stack SHALL bind a public interface or be
routed through the public site's reverse proxy.

#### Scenario: Services survive reboot
- **WHEN** the droplet reboots
- **THEN** Compose services restart automatically and health checks report
  ready without manual intervention

#### Scenario: OpenCode requires auth
- **WHEN** an unauthenticated request reaches the OpenCode server port
- **THEN** it is rejected with an authentication challenge

#### Scenario: Backlog stays loopback on the host
- **WHEN** the Backlog browser server runs on the droplet
- **THEN** it binds loopback (or Tailscale interface via the approved proxy
  path) and is not reachable from the public internet

### Requirement: Capacity measurement and sizing gate
The 4 vCPU / 8 GiB sizing SHALL be verified under real load: baseline idle
metrics, then at least one representative OpenCode session and one Backlog
browser session, with RAM/CPU/disk recorded. If measurements show the sizing
insufficient, a sizing revision proposal is required — the deployment SHALL NOT
self-escalate resources or spend.

#### Scenario: Baseline and load recorded
- **WHEN** qualification completes
- **THEN** idle and under-session metrics (memory, CPU, disk) are recorded in
  the change evidence and the sizing decision is revisited on evidence

### Requirement: Cost and provisioning authorization gate
Droplet creation (~$48/mo) SHALL proceed only after an explicit approval
decision (sizing, region, monthly cost) recorded in the ledger. The compose
stack and bootstrap profile SHALL be testable on a local container or VM
before any paid provisioning.

#### Scenario: Local pre-validation before spend
- **WHEN** the compose stack is ready
- **THEN** it has been validated locally (equivalent container/VM) before any
  droplet is created; the approval decision cites the local evidence

### Requirement: Lifecycle, recovery, and backup boundaries
The host SHALL use ordinary service management (systemd/Compose restart
policies) — no custom supervisor. Process restart MUST NOT be treated as work
recovery: sessions and their state are recoverable per OpenCode semantics, and
unpushed/unsynced artifacts live in Git. The droplet's persistent state (OpenCode
sessions, Backlog files, cloned vaults/repos) SHALL have a documented backup
path (off-host or snapshot) whose restore procedure is tested before the host
is considered authoritative for anything.

#### Scenario: Session survives disconnect, not necessarily reboot
- **WHEN** the laptop disconnects
- **THEN** server-side OpenCode sessions persist and can be reattached; this is
  session continuity, not a crash-recovery guarantee

#### Scenario: Restore procedure exists before authority
- **WHEN** the host is designated authoritative for the ledger (change 5
  depends on this)
- **THEN** a tested backup/restore path for its persistent state exists and its
  most recent successful test is recorded