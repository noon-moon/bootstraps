# Fixture Host Runbook

Operator instructions, not authorization to deploy. Use an approved Ubuntu
24.04 host and a reviewed, clean, root-owned checkout at
`/opt/bootstraps-release`. Keep the approved full revision independently;
do not derive approval from whatever happens to be checked out. Materialize
the private context at `/var/lib/bootstraps/context`; see
[deployment.schema.md](example-context/deployment.schema.md). No real ledger,
provider credentials, public-site changes, or global network-policy changes
are part of this procedure.

## Prepare

Run host commands as root in Bash, without shell tracing. Set `REV` to the
approved full revision. The context must register exactly one synthetic,
non-authoritative fixture at the path below and seven short role model IDs.

```bash
set -euo pipefail
: "${REV:?Set the independently approved full source revision}"
SOURCE=/opt/bootstraps-release
CONTEXT=/var/lib/bootstraps/context
FIXTURE=/home/agent/dev/agent-workspace/backlog-fixture
provision() {
  python3 "$SOURCE/deploy/scripts/provision-host.py" "$@" \
    --source "$SOURCE" --context "$CONTEXT" --expect-rev "$REV" \
    --fixture-dir "$FIXTURE"
}
compose() {
  python3 -B "$SOURCE/deploy/scripts/workspace.py" compose "$@"
}
provision validate
```

On a fresh, explicitly authorized fixture host only, run `provision packages`,
`provision user`, `provision bootstrap`, then `provision env`, checking each
result. These are separate root provisioning actions; the runtime user gets
no sudo or Docker-group grant. Never use the `env` stage to relabel existing
unmarked data as a fixture. On an existing host, retain the fixture marker
and runtime password; do not rerun initialization against ambiguous data.

For an existing env file, this root-only recipe adds missing path references
without rewriting or printing the password. It refuses symlinks, wrong
ownership/mode, duplicate settings and conflicting paths. Stop other env
editors first; do not shell-source the env file or print `compose config`.

```bash
python3 - <<'PY'
import os, stat
assert os.geteuid() == 0, "root required"
path = "/etc/bootstraps/runtime.env"
fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
with os.fdopen(fd, "r+", encoding="utf-8", newline="") as f:
    st = os.fstat(f.fileno())
    assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1
    assert (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, 0o600)
    original = f.read()
    values = {}
    for line in original.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        assert sep and key not in values, "invalid/duplicate env setting"
        values[key] = value
    assert values.get("OPENCODE_SERVER_PASSWORD"), "retain an existing password"
    expected = {"BOOTSTRAPS_SOURCE_DIR": "/opt/bootstraps-release",
                "RENDERED_CONFIG_DIR": "/var/lib/bootstraps/runtime-config"}
    assert values.get("RUNTIME_CONFIG_DIR", expected["RENDERED_CONFIG_DIR"]) == expected["RENDERED_CONFIG_DIR"]
    assert values.get("BACKLOG_DATA_DIR") == "/home/agent/dev/agent-workspace/backlog-fixture"
    for key, value in expected.items():
        assert key not in values or values[key] == value, "conflicting runtime path"
    missing = [key + "=" + value + "\n" for key, value in expected.items() if key not in values]
    if missing:
        f.write(("\n" if original and not original.endswith("\n") else "") + "".join(missing))
        f.flush()
        os.fsync(f.fileno())
PY
```

## Build And Start

`prepare-host.sh` validates, renders and builds with **base, gate, and any validated workspace override**;
it does not start containers or repoint Serve. Rendering refuses edited or
legacy unmanaged output: preserve it separately before authorizing a fresh
render. Skill links use the same absolute read-only source path on host and
container. The effective config is `opencode/opencode.json`.

```bash
sh "$SOURCE/deploy/scripts/prepare-host.sh" --expect-rev "$REV"
# Equivalent build step, if needed separately: compose build
# Fresh marked fixture only, after build and before first up:
# provision fixture
compose config --quiet
compose up -d --force-recreate --wait
python3 "$SOURCE/deploy/scripts/verify-host.py" \
  --source "$SOURCE" --env-file /etc/bootstraps/runtime.env \
  --report /root/fixture-verify-report.json
```

The verifier checks actual API discovery of seven roles, nine skills and
model bindings, auth, fixture task/session identity and restart persistence.
It writes only fixture sentinels/sessions; it sends no inference prompts.
After any render, recreate containers: restarting alone retains old file-bind
inodes. For a routine restart without config changes, use the same validated
`compose` function in order: `compose restart backlog`, `compose restart relay`,
`compose restart opencode`, `compose restart gate`; rerun the verifier.

## Gate Checks

Complete these checks **before repointing Serve**. Both gate listeners must
be only `127.0.0.1:17420` (Backlog) and `127.0.0.1:17443` (OpenCode); backend
publishes remain loopback-only at 16420 and 14096. Inspect `ss -ltnp` and
`compose ps`: four healthy services, no new admin listener on 2019. Gate
health deliberately expects 403 without XFF on both ports, not 200.
A stock-image syntax check is not hardened-runtime proof. If Caddy cannot
execute under the declared UID/capabilities (for example, `operation not
permitted`), stop qualification; do not silently relax the security settings.

As root, choose `ALLOWED_IP` from the private context's exact allow-list and
`DENIED_IP` as a distinct documentation/test IP absent from that list. Do not
add loopback or a range to the allow-list just to make tests pass. For each
port, exercise this matrix with `curl --noproxy '*' -sS -o /dev/null -w
'%{http_code}\n'` and the indicated `-H` headers:

| Request | Backlog `http://127.0.0.1:17420/` | OpenCode `http://127.0.0.1:17443/global/health` |
| --- | --- | --- |
| `X-Forwarded-For: $ALLOWED_IP` | 200 | 401 without Basic auth; 200 with valid auth |
| `X-Forwarded-For: $DENIED_IP` | 403 | 403 |
| No XFF | 403 | 403 |
| Allowed XFF plus `Tailscale-Funnel-Request: true` | 403 | 403 |
| Spoof chain `X-Forwarded-For: $ALLOWED_IP, $DENIED_IP` | 403 | 403 |

Use the existing verifier for authenticated checks; do not put the password
in a command argument, transcript or report. For the Backlog WebSocket path:

```bash
ws_rc=0
curl --noproxy '*' --http1.1 -i -N --max-time 3 \
  -H "X-Forwarded-For: $ALLOWED_IP" \
  -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Version: 13' \
  -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
  http://127.0.0.1:17420/ || ws_rc=$?
test "$ws_rc" -eq 0 || test "$ws_rc" -eq 28
```

Require 101, `Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`, and a
server frame. A timeout after a verified upgrade is expected for an open
socket, not a substitute for those checks. Repeat the upgrade with denied,
missing, spoof-chain and Funnel headers: require 403, never 101. Check the
same deny rules on OpenCode's `/event` SSE path. An HTTP 200 alone is not WS
or SSE evidence.

These root-loopback header probes test the gate protocol, **not actual phone
identity**: root is in the trusted immediate-proxy position. Tailscale
1.102.3 `addProxyForwardedHeaders` overwrites XFF with the connection source;
Caddy trusts only immediate `127.0.0.1/32` with `trusted_proxies_strict`.
Inspect existing Serve configuration; do not reset unrelated services.
Only after startup, verification and gate checks pass:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:17420
tailscale serve --bg --https=8443 http://127.0.0.1:17443
tailscale serve status
```

Reconfirm the board and WebSocket from the allowed phone/laptop over their
real tailnet connections, and 403 from a non-allowed tailnet device even
when it supplies spoofed allowed XFF. Earlier phone/board proof may need
reconfirmation after this deployment. OpenCode still requires Basic auth.
This is an **application-only** allow-list: a broad global tailnet ACL is
still broad. No global ACL, public firewall, public Caddy or Funnel policy
is rewritten here. A stopped gate fails closed for these Serve routes.

## Backup And Restore

Install standard `age` on the **host**, through a separately authorized
operator package action (`apt-get install age`); the backup unit requires
`/usr/bin/age`. No age container is used. Install age on the operator laptop
as well. Generate a new private key **only locally**, directly into a file:

```bash
# Operator laptop, never a remote shell; do not overwrite an existing key.
umask 077
KEYDIR="$HOME/.config/bootstraps-backup"
install -d -m 700 "$KEYDIR"
age-keygen -o "$KEYDIR/identity.agekey"
age-keygen -y "$KEYDIR/identity.agekey"  # PUBLIC recipient only
```

Put only that public recipient in private-context `deployment.json` under
`backup.recipient`. Never print the private key, send it over SSH, or place
it on the host. Preserve a separate secure local key backup. After real
fixture task/session evidence exists, run this on the host:

```bash
install -d -o root -g root -m 700 /var/lib/bootstraps/backups
python3 "$SOURCE/deploy/scripts/backup-fixture.py" \
  --source "$SOURCE" --env-file /etc/bootstraps/runtime.env \
  --context "$CONTEXT" --rendered /var/lib/bootstraps/runtime-config \
  --deployment "$CONTEXT/deployment.json" \
  --backup-dir /var/lib/bootstraps/backups --project t444host
```

Backup uses both Compose files internally to stop all four services and
resume them in order, requiring health before publishing success. It streams
tar into host age without a plaintext backup archive at rest. Ciphertext and
manifest are 0600 in a root-owned 0700 directory; retention is fixed at seven
owned pairs (there is no `--keep` flag). Auth material is excluded. Pull the
selected `.tar.age` **and** `.manifest.json` via authenticated SCP to a local
0700 directory, retain their provenance, and verify the ciphertext SHA-256
against the retained manifest. Do not trust a replacement manifest obtained
from an untrusted source.

Restore uses a disposable UUID project, base Compose only (deliberately no
gate or host network), distinct loopback ports 24096/26420 and fresh runtime
auth. Use a Linux host with the **same clean source revision** at
`/opt/bootstraps-release` as `source_rev` in the manifest and the recorded
immutable image IDs already available. The archive does not contain images
or the checkout. Do not overwrite a live checkout to make it match; use a
separately prepared restore host if necessary.

On the laptop, set `HOST` to the authorized SSH alias, `CIPHER` and `MANIFEST`
to the retained local files, and `PLAIN_SHA` to the trusted manifest's
`plaintext_sha256`. Copy the manifest, not the key, to the restore host:

```bash
# Operator laptop, Bash; only plaintext TAR bytes cross SSH stdin.
set -euo pipefail
: "${HOST:?}" "${CIPHER:?}" "${MANIFEST:?}" "${PLAIN_SHA:?}"
[[ "$PLAIN_SHA" =~ ^[0-9a-f]{64}$ ]]
ssh "root@$HOST" 'install -d -o root -g root -m 700 /root/fixture-restore'
scp "$MANIFEST" "root@$HOST:/root/fixture-restore/selected.manifest.json"
ssh "root@$HOST" 'chmod 600 /root/fixture-restore/selected.manifest.json'
age --decrypt --identity "$KEYDIR/identity.agekey" "$CIPHER" | \
  ssh "root@$HOST" "python3 /opt/bootstraps-release/deploy/scripts/restore-fixture.py \
    --tar-stdin --expect-sha256 '$PLAIN_SHA' \
    --manifest /root/fixture-restore/selected.manifest.json \
    --source /opt/bootstraps-release"
```

Require both pipeline success and the restore success message: pre-existing
task/session identities verified, restore containers/volumes/network removed,
and temporary plaintext removed. Restore temporarily stores decrypted tar
and extracted data in root-only scratch, then removes it in `finally`; it
does not leave a running test stack. Cleanup failure is a failed round-trip.
After interruption, inspect exact owned resources and scratch before retry;
never use an unscoped `down -v`, prune, or delete live resources. Keep the
local ciphertext, key, manifest and evidence; remove the uploaded manifest
when no longer needed.

## Units And Recovery

Install the reviewed units root-owned 0644, then reload systemd:

```bash
install -o root -g root -m 644 "$SOURCE/deploy/systemd/t444host-compose.service" /etc/systemd/system/
install -o root -g root -m 644 "$SOURCE/deploy/systemd/t444host-backup.service" /etc/systemd/system/
install -o root -g root -m 644 "$SOURCE/deploy/systemd/t444host-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable t444host-compose.service
```

The Compose unit includes both files; backup.service invokes the same
two-file backup orchestration. Unit installation is not round-trip proof.
**Only after a real Linux backup/decrypt/restore/cleanup round-trip passes**,
enable `systemctl enable --now t444host-backup.timer`. The timer is every
15 minutes with missed-run catch-up, not continuous availability. Check
`systemctl status t444host-backup.service` and `systemctl list-timers` for
actual success; an unhealthy running container does not auto-heal.

Off-host copying is not automated here. RPO depends on successful backups
**and** the last verified off-host copy: laptop offline means no new off-host
copy, and host loss can destroy all newer local snapshots. Seven local pairs
are retention, not an HA or disaster-recovery guarantee. No inference load
or model authentication is qualified by this fixture procedure.

## Operator Repository Workspace

This optional seam clones only an explicitly authorized private-context allowlist.
It does not move `/opt/bootstraps-release`, initialize/copy/repoint a ledger,
scan vault semantics, request inference, or change the website host or DNS.
Repository registration and root `AGENTS.md`/`projects.json` remain operator-owned
context work, separate from cloning. Do not start project work until its backup
coverage has been explicitly addressed.

Materialize root-owned `repositories.json` in `/var/lib/bootstraps/context`:

```json
{
  "schema": 1,
  "repositories": [
    {"name": "demo", "url": "git@github.com:exampleorg/demo.git", "branch": "main"}
  ]
}
```

These are exact fields, not executable configuration. Entries must be unique,
use one authorized GitHub owner, typed SSH URLs ending in `.git`, and explicit
default branches. The helper verifies the branch against `ls-remote --symref`;
it never infers the repository inventory. Pass each authorized name explicitly.

Before invocation, the operator must register a **read-only, repository-specific
deploy key** for each selected repository and materialize it at
`/etc/bootstraps/repo-ssh/<name>` (UID 10001, mode 0400). Materialize verified
GitHub host keys from the GitHub meta API as `known_hosts` with the same ownership
and mode. The enclosing directory must be root-owned 0700: host UID 2201 cannot
read the keys. Do not use agent forwarding, broad tokens, or TOFU host keys.
The helper checks all selected files before writes but does not register keys
or certify their remote permissions.

Keep `/home/agent/dev` UID 2201-owned 0755. It must already contain regular
`AGENTS.md` and `projects.json`. New checkout directories, `.git-metadata`, and
`worktrees` become UID/GID 10001-owned; the two shared writable directories use
0700. Only empty unregistered paths may be adopted. No recursive chown occurs.
Completed clones get root-owned receipts in `/var/lib/bootstraps/repositories`.
Unknown nonempty paths, symlinks, foreign origins, wrong branches, and dirty
canonical checkouts are refused. Failed/partial clones are not adopted or
cleaned up automatically; inspect them as an operator before retrying.

Build the updated OpenCode image first (Git, OpenSSH, Git LFS, and Python are
build-time dependencies, never startup installs). Record the **old and new image
IDs** explicitly when rebuilding an existing version tag; preserve old local
images for backups whose manifests refer to those IDs. Never auto-prune them.
Use a reviewed root-owned source checkout and a maintenance window with OpenCode
stopped, so workers cannot race refresh or host path checks. Run as root:

```sh
python3 -B /opt/bootstraps-release/deploy/scripts/workspace.py \
  --manifest /var/lib/bootstraps/context/repositories.json \
  --image bootstraps-opencode:1.18.29 demo
python3 -B /opt/bootstraps-release/deploy/scripts/workspace.py compose config --quiet
python3 -B /opt/bootstraps-release/deploy/scripts/workspace.py compose up -d --wait
```

The same first command refreshes existing receipted repositories, **fetch-only**:
it does not advance canonical checkout HEAD, reset, stash, merge, or purge.
JSON evidence contains name/path/branch/HEAD/remote, fetched HEAD verified against
`ls-remote`, clean status, and LFS fetch/fsck status, never note contents or keys.
Transport/LFS failure is fatal and output is withheld; do not label partial
results complete. Private GitHub/LFS authentication still requires host-side
qualification with the authorized keys. Submodules are not recursively cloned.

After all manifest entries have matching completed receipts, the helper writes
root-only `/var/lib/bootstraps/workspace.compose.json`. Normal provisioning,
verification, fixture backup, and the updated systemd unit validate and include
this optional override. Install the updated unit using the approved-unit upgrade
path and daemon-reload; an old unit will not use this seam. Fixture-only setups
work without the override. Isolated restore deliberately does **not** include it.

OpenCode works at `/home/agent/dev` with the whole dev root bound read-only,
overlaid by RW `.git-metadata` and `worktrees` binds at identical absolute paths.
Existing `/workspace`, `/data`, source/config binds, and the exact three named
volumes remain intact. No host home subtree or SSH keys are mounted into OpenCode.
The one-shot helper alone receives a selected checkout, the metadata/worktree
parents, and the selected key plus known-hosts file. It runs UID 10001, isolated
temporary HOME/Git configuration, read-only rootfs, dropped capabilities, and
no-new-privileges, without a Docker socket. Root never executes Git against these
mutable repositories. Before refresh, an explicit local Git-config allowlist
rejects added includes, filters, proxies, and custom LFS transports rather than
executing agent-supplied configuration in the key-bearing helper.

Worker example (substitute an authorized canonical name/default branch):

```sh
git -C /home/agent/dev/demo worktree add -b task/demo /home/agent/dev/worktrees/demo origin/main
```

Canonical **source files** are mount-protected, not Git references: metadata is
intentionally writable so normal worktrees work. This is not hard branch
authorization or immutable refs. Workers lack deploy keys; normal fetch/push
reports `operator refresh required`. Do not promise autonomous fetch or push.

**Backup gap:** fixture backup still covers only its explicit fixture/runtime
roots, selected context metadata, and three named volumes. It does **not** protect
`~/dev` clones, Git metadata, project working trees, the generated workspace
override/receipts, or deploy keys. Restoring a fixture never mounts live private
repositories. Establish a separately authorized project-WIP backup before real work.
