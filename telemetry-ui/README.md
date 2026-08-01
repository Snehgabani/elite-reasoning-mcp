# Local Telemetry UI

This is a read-only local dashboard for an Elite Reasoning MCP brain. Its server actions read local SQLite files directly; it is not designed for Vercel or another remote deployment.

## Run locally

```bash
npm ci
ELITE_BRAIN_DIR="$HOME/.elite-reasoning/brain" npm run dev
```

`ELITE_BRAIN_DIR` is preferred. `BRAIN_DIR` remains supported for existing local setups. If neither is set, the dashboard uses `~/.elite-reasoning/brain`.

Keep the dashboard bound to a trusted local interface and do not expose it through a public tunnel. The UI inherits access to the local brain, which can contain private project memory even though secrets are redacted before storage.
