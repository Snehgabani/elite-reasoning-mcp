# Repository Security Controls

This repository contains workflow files for CI, CodeQL, dependency review, Dependabot, release provenance, and PyPI Trusted Publishing. GitHub repository settings must enforce the remaining controls.

## Main Branch

Configure a branch protection or ruleset for `main` that requires:

- Pull requests before merge, with at least one maintainer review.
- Dismissal of stale approvals after new commits.
- Passing `CI / test` checks for supported Python versions.
- Passing CodeQL and Dependency Review checks when GitHub exposes them for the repository.
- Required code-owner review for `.github/`, `pyproject.toml`, `uv.lock`, MCP integration, and memory changes.
- Conversation resolution before merge.
- Linear history where the maintainer workflow permits it.
- No force pushes or branch deletion.
- No bypass actors except a documented emergency maintainer path.

## Secrets And Actions

- Enable GitHub secret scanning and push protection for the repository. The repository also runs an independent, checksum-verified Gitleaks history and working-tree scan in read-only CI; GitHub-native push protection remains necessary to stop a secret before it reaches any commit.
- Enable Dependabot alerts, security updates, and grouped-update review policies.
- Restrict Actions to GitHub-verified or explicitly allowlisted actions; keep SHA pins current through Dependabot.
- Require approval for first-time contributors and keep fork pull-request workflows read-only.
- Do not use self-hosted runners for untrusted pull requests.
- Store PyPI publishing only in the protected `release` environment and use Trusted Publishing/OIDC, never a long-lived PyPI token.

## Release Checklist

Before publishing a tag, verify:

1. `uv run python scripts/release_check.py` passes from the release commit.
2. `uv lock --check` succeeds, the Secret Scan workflow passes, and Dependabot security alerts are triaged.
3. The tag is `v<pyproject version>` and the changelog documents user-visible and security changes.
4. The release environment requires approval and provenance/attestation jobs completed.
5. The package’s `elite-reasoning-mcp --version` and `elite-reasoning-mcp doctor --json` report the intended runtime identity after installation.
