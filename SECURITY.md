# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | ✅         |

## Security Model

Elite Reasoning MCP is designed with security as a core principle:

- **Local-only execution**: All processing happens on your machine
- **No network calls**: The MCP server makes zero outbound requests
- **No telemetry**: No usage data is collected, transmitted, or stored remotely
- **SQLite storage**: All data is stored in a local SQLite database you own
- **No API keys required**: The system runs without any external service dependencies

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public GitHub issue**
2. Email: [snehgabani@users.noreply.github.com](mailto:snehgabani@users.noreply.github.com)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work on a fix immediately.

## Data Privacy

- All prompt data stays on your local machine
- Anti-patterns, decisions, and quality scores are stored locally in `brain/elite.db`
- No data is ever transmitted to external servers
- You can delete all stored data at any time by removing the `brain/` directory
