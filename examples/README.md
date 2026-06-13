# Examples

Real-world usage patterns for Elite Reasoning MCP.

## Basic: Orchestrate Every Prompt

The simplest integration — call `orchestrate_request_tool` on every prompt:

```json
{
  "tool": "orchestrate_request_tool",
  "arguments": {
    "user_prompt": "Fix the authentication bug in the login flow"
  }
}
```

**Response:** Returns an execution plan with intent classification, relevant past mistakes, recommended tools, and a pre-flight checklist.

## Anti-Pattern Memory

Record a mistake so the LLM never repeats it:

```json
{
  "tool": "record_mistake",
  "arguments": {
    "mistake": "Forgot to handle null response from API",
    "root_cause": "No defensive coding check on external call",
    "fix": "Always wrap external API calls with null/error checks",
    "severity": "high"
  }
}
```

Later, before any coding task:

```json
{
  "tool": "check_anti_patterns",
  "arguments": {
    "description": "Making an API call to fetch user data"
  }
}
```

**Response:** "⚠️ Past mistake: Forgot to handle null response from API. Fix: Always wrap external API calls with null/error checks."

## Decision Council

Get 5 adversarial perspectives before making a major decision:

```json
{
  "tool": "decision_council_review",
  "arguments": {
    "decision": "Migrate from REST to GraphQL",
    "perspectives": [
      "What are the performance implications?",
      "How does this affect our team's velocity?",
      "What's the migration risk?"
    ]
  }
}
```

## Confidence Calibration

Track prediction accuracy over time:

```json
{
  "tool": "calibration_predict",
  "arguments": {
    "prediction": "This refactor will not break any existing tests",
    "confidence": 0.85,
    "category": "refactoring"
  }
}
```

After the refactor:

```json
{
  "tool": "calibration_resolve",
  "arguments": {
    "prediction_id": 1,
    "outcome": true
  }
}
```

Check your calibration score:

```json
{
  "tool": "calibration_score",
  "arguments": {}
}
```

## FMEA Risk Analysis

Analyze failure modes before building:

```json
{
  "tool": "fmea_analysis",
  "arguments": {
    "component": "User Authentication Service",
    "failure_modes": [
      "Token expiration not handled",
      "Rate limiting bypass",
      "Session fixation attack",
      "Password reset flow abuse"
    ]
  }
}
```

## Five Whys Root Cause Analysis

Dig into the root cause of a bug:

```json
{
  "tool": "five_whys",
  "arguments": {
    "problem": "Users are seeing 500 errors on the dashboard",
    "initial_why": "The API endpoint is timing out"
  }
}
```

## IDE Configuration Examples

### Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "bash",
      "args": ["-c", "cd ~/.elite-reasoning && uv run python -m core.integration.mcp_server"]
    }
  }
}
```

### Claude Desktop (App Settings → MCP)

```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "bash",
      "args": ["-c", "cd ~/.elite-reasoning && uv run python -m core.integration.mcp_server"]
    }
  }
}
```

### Windows (any IDE)

```json
{
  "mcpServers": {
    "elite-reasoning": {
      "command": "cmd",
      "args": ["/c", "%USERPROFILE%\\.elite-reasoning\\scripts\\run_elite_mcp.bat"]
    }
  }
}
```
