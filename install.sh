#!/usr/bin/env bash
# Install the published package without executing a remote bootstrap script.
set -euo pipefail

readonly PACKAGE_NAME="elite-reasoning-mcp"
configure_gemini=false
version="${ELITE_REASONING_MCP_VERSION:-}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [--version VERSION] [--configure-gemini]

Installs Elite Reasoning MCP into uv's isolated tool environment.

Options:
  --version VERSION       Install an exact package version.
  --configure-gemini      Add or update the Gemini CLI MCP server entry.
  -h, --help              Show this help text.

Set ELITE_GEMINI_CONFIG to override the default Gemini MCP config path.
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --version)
            if (( $# < 2 )); then
                echo "--version requires a value" >&2
                exit 2
            fi
            version="$2"
            shift 2
            ;;
        --configure-gemini)
            configure_gemini=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

package_spec="$PACKAGE_NAME"
if [[ -n "$version" ]]; then
    package_spec+="==$version"
fi

uv tool install --reinstall "$package_spec"
mkdir -p "$HOME/.elite-reasoning/brain"

if [[ "$configure_gemini" == true ]]; then
    config_path="${ELITE_GEMINI_CONFIG:-$HOME/.gemini/config/mcp_config.json}"
    python3 - "$config_path" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Refusing to overwrite invalid JSON at {config_path}: {error}")
else:
    config = {}

if not isinstance(config, dict):
    raise SystemExit(f"Refusing to overwrite non-object JSON at {config_path}")

servers = config.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    raise SystemExit(f"Refusing to overwrite non-object mcpServers at {config_path}")

servers["elite-reasoning"] = {
    "command": "elite-reasoning-mcp",
    "args": [],
    "env": {"ELITE_BRAIN_DIR": str(Path.home() / ".elite-reasoning" / "brain")},
}

temporary_path = config_path.with_suffix(f"{config_path.suffix}.tmp")
temporary_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary_path.replace(config_path)
print(f"Configured Gemini CLI MCP server in {config_path}")
PY
fi

echo "Elite Reasoning MCP is installed. Add the 'elite-reasoning-mcp' command to your MCP client."
