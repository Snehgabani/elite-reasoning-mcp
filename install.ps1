# ╔══════════════════════════════════════════════════════════════╗
# ║  Elite Reasoning MCP — Windows One-Command Installer        ║
# ║  Makes any LLM think harder. 66 tools. Any model.           ║
# ╚══════════════════════════════════════════════════════════════╝
#
# USAGE (paste in PowerShell):
#   irm https://raw.githubusercontent.com/YOUR_REPO/main/install.ps1 | iex
#   — OR —
#   .\install.ps1
#

$ErrorActionPreference = "Stop"
$EliteDir = "$env:USERPROFILE\.elite-reasoning"
$BrainDir = "$EliteDir\brain"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  🧠 Elite Reasoning MCP — Windows Installer  ║" -ForegroundColor Cyan
Write-Host "║  66 tools · Works with any model             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Install uv ────────────────────────────────
Write-Host "→ Checking prerequisites..." -ForegroundColor Yellow
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing uv (Python package manager)..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
Write-Host "  ✅ uv ready" -ForegroundColor Green

# ── Step 2: Setup directory ───────────────────────────
Write-Host "→ Setting up Elite Reasoning MCP..." -ForegroundColor Yellow
if (-not (Test-Path $EliteDir)) {
    New-Item -ItemType Directory -Path $EliteDir -Force | Out-Null
}
New-Item -ItemType Directory -Path $BrainDir -Force -ErrorAction SilentlyContinue | Out-Null

# If we got here via zip extraction, files are already in place
# If from git clone, they're also in place
Write-Host "  ✅ Directory ready: $EliteDir" -ForegroundColor Green

# ── Step 3: Create Windows runner script ──────────────
Write-Host "→ Creating runner script..." -ForegroundColor Yellow
$runnerContent = @'
@echo off
REM Elite MCP Server — Windows Launcher
cd /d "%~dp0"

set BRAIN_DIR=%~dp0brain
if not exist "%BRAIN_DIR%" mkdir "%BRAIN_DIR%"

where uv >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set UV_BIN=%USERPROFILE%\.local\bin\uv.exe
    ) else (
        echo ERROR: uv not found. Install with: irm https://astral.sh/uv/install.ps1 ^| iex
        exit /b 1
    )
) else (
    set UV_BIN=uv
)

%UV_BIN% run --with mcp --with fastmcp python -c "import sys; sys.path.append('.'); from core.integration.mcp_server import create_mcp_server; server = create_mcp_server('%BRAIN_DIR%'); server.run()" 2>> "%~dp0mcp_error.log"
'@
Set-Content -Path "$EliteDir\run_elite_mcp.bat" -Value $runnerContent -Encoding ASCII

# Also create a .cmd version
Copy-Item "$EliteDir\run_elite_mcp.bat" "$EliteDir\run_elite_mcp.cmd" -Force

Write-Host "  ✅ Runner scripts created" -ForegroundColor Green

# ── Step 4: Configure IDE ─────────────────────────────
Write-Host "→ Configuring IDE..." -ForegroundColor Yellow

# Detect which IDEs are installed
$configs = @{
    "Antigravity" = "$env:USERPROFILE\.gemini\config\mcp_config.json"
    "Cursor"      = "$env:USERPROFILE\.cursor\mcp.json"
    "Claude"      = "$env:APPDATA\Claude\claude_desktop_config.json"
    "VSCode"      = "$env:USERPROFILE\.continue\config.json"
}

$configured = $false
foreach ($ide in $configs.GetEnumerator()) {
    $configPath = $ide.Value
    $configDir = Split-Path $configPath

    if (Test-Path $configDir) {
        Write-Host "  Found $($ide.Key) at $configDir" -ForegroundColor Gray

        if (Test-Path $configPath) {
            $json = Get-Content $configPath -Raw | ConvertFrom-Json

            # Check if elite-reasoning already exists
            $serverProp = if ($ide.Key -eq "Cursor" -or $ide.Key -eq "Claude") { "mcpServers" } else { "mcpServers" }

            if (-not $json.$serverProp) {
                $json | Add-Member -NotePropertyName $serverProp -NotePropertyValue @{} -Force
            }

            if (-not $json.$serverProp."elite-reasoning") {
                $json.$serverProp | Add-Member -NotePropertyName "elite-reasoning" -NotePropertyValue @{
                    command = "$EliteDir\run_elite_mcp.bat"
                } -Force
                $json | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
                Write-Host "  ✅ Added elite-reasoning to $($ide.Key)" -ForegroundColor Green
                $configured = $true
            } else {
                Write-Host "  ✅ $($ide.Key) already configured" -ForegroundColor Green
                $configured = $true
            }
        } else {
            # Create new config
            $newConfig = @{
                mcpServers = @{
                    "elite-reasoning" = @{
                        command = "$EliteDir\run_elite_mcp.bat"
                    }
                }
            }
            New-Item -ItemType Directory -Path $configDir -Force -ErrorAction SilentlyContinue | Out-Null
            $newConfig | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
            Write-Host "  ✅ Created config for $($ide.Key)" -ForegroundColor Green
            $configured = $true
        }
    }
}

if (-not $configured) {
    Write-Host "  ⚠️  No supported IDE found. Manually add to your IDE's MCP config:" -ForegroundColor Yellow
    Write-Host "     { ""elite-reasoning"": { ""command"": ""$EliteDir\run_elite_mcp.bat"" } }" -ForegroundColor White
}

# ── Step 5: Add enforcement to GEMINI.md ──────────────
$geminiMd = "$env:USERPROFILE\.gemini\GEMINI.md"
$geminiDir = "$env:USERPROFILE\.gemini"

if (Test-Path $geminiDir) {
    $enforcement = @"

# Global Instructions

## ⚡ RULE #0 — ELITE MCP PIPELINE

On EVERY user message, your FIRST tool call MUST be:

``````
call_mcp_tool(
  ServerName="elite-reasoning",
  ToolName="orchestrate_request_tool",
  Arguments={"user_prompt": "<the user's exact message>"}
)
``````

No exceptions except "ok", "thanks", "yes", "no". This fires the 66-tool reasoning pipeline.
"@

    if (Test-Path $geminiMd) {
        $content = Get-Content $geminiMd -Raw -ErrorAction SilentlyContinue
        if ($content -notmatch "orchestrate_request_tool") {
            Add-Content -Path $geminiMd -Value $enforcement
            Write-Host "  ✅ GEMINI.md updated with enforcement rule" -ForegroundColor Green
        }
    } else {
        Set-Content -Path $geminiMd -Value $enforcement
        Write-Host "  ✅ GEMINI.md created with enforcement rule" -ForegroundColor Green
    }
}

# ── Step 6: Copy schemas ─────────────────────────────
$schemaSource = "$EliteDir\schemas"
$schemaTarget = "$env:USERPROFILE\.gemini\antigravity\mcp\elite-reasoning"

if ((Test-Path $schemaSource) -and (Test-Path "$env:USERPROFILE\.gemini\antigravity")) {
    New-Item -ItemType Directory -Path $schemaTarget -Force -ErrorAction SilentlyContinue | Out-Null
    Copy-Item "$schemaSource\*" $schemaTarget -Force
    Write-Host "  ✅ Tool schemas installed" -ForegroundColor Green
}

# ── Done ──────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ Installation Complete!                    ║" -ForegroundColor Green
Write-Host "║                                              ║" -ForegroundColor Green
Write-Host "║  NEXT: Restart your IDE and start a new      ║" -ForegroundColor Green
Write-Host "║  conversation. Every prompt will now go       ║" -ForegroundColor Green
Write-Host "║  through the elite reasoning pipeline.        ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
