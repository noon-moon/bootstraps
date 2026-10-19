# deployment.json schema (private context; parent authors real values)

```json
{
  "access": {
    "allowed_client_ips": [
      "192.0.2.10",
      "192.0.2.11",
      "2001:db8::10"
    ]
  },
  "backup": {
    "recipient": "age1...operator-public-key...",
    "keep": 7
  }
}
```

## access.allowed_client_ips

- list of EXACT client IP addresses (single /32 or /128 each; ranges and
  hostnames are rejected at render time).
- These are tailnet IPs of the user's devices (phone, laptop) plus any
  IPv6 the parent supplies. Never embed instance values in the public
  repo — this file documents the shape only. The addresses above are
  documentation ranges, not actual tailnet devices; substitute the exact
  authorized device addresses from the private context.
- The gate (Caddy >= 2.8) trusts only the immediate loopback proxy
  (Tailscale Serve) and matches the rightmost X-Forwarded-For value, so
  client-supplied spoofed XFF is ignored. Everything not matching is 403
  on all paths/methods; the Tailscale Funnel request marker is rejected.

## backup

- `recipient`: the operator's age PUBLIC key (age1…). The private key
  never lives on the host or in git; decryption happens operator-side
  with a local identity file. Only decrypted tar bytes cross SSH stdin to
  the restore process; never send the private key.
- `keep`: the example records the retention policy of seven local pairs.
  The current backup implementation fixes retention at seven; it does not
  read this field or accept a `--keep` flag.

No provider API keys belong here; model ids are names only and never
authenticate anything.

## Runtime Publication

The renderer requires exactly seven short role IDs in `models.json` and
exactly one shared Backlog fixture registration in `resources.json` (the
group name may be `global`). Its path must match `--backlog-fixture`, either
absolutely or relative to `/home/agent/dev`. The existing marker must declare
`SYNTHETIC FIXTURE` and `non-authoritative` or `NOT the authoritative ledger`.
There is no path-check bypass and the renderer never creates a ledger.

Rendering stages a complete tree and atomically exchanges directories on
Linux/macOS. Re-rendering refuses edited or legacy unmanaged output rather
than discarding it; preserve that directory at a separate operator-chosen
path before generating a fresh tree. Recreate containers after rendering
(`up -d --wait --force-recreate`): existing file binds retain old inodes.

Both Compose files accept `RUNTIME_CONFIG_DIR`, falling back to the existing
`RENDERED_CONFIG_DIR` contract and then `/var/lib/bootstraps/runtime-config`.
`BOOTSTRAPS_SOURCE_DIR` defaults to `/opt/bootstraps-release` and is mounted
read-only at the identical absolute container path. Use only synthetic
credentials for local tests. The gate has no admin listener or persistent
certificate storage; its healthcheck requires an unauthenticated 403 from
both loopback listeners without disclosing or bypassing the allow-list.
