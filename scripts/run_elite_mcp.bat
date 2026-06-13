@echo off
REM Elite MCP Server — Windows Launcher
REM Works for ANY user on ANY machine.

cd /d "%~dp0"

set BRAIN_DIR=%~dp0brain
if not exist "%BRAIN_DIR%" mkdir "%BRAIN_DIR%"

set LOG_FILE=%~dp0mcp_error.log

REM Auto-detect uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set UV_BIN=%USERPROFILE%\.local\bin\uv.exe
    ) else if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
        set UV_BIN=%USERPROFILE%\.cargo\bin\uv.exe
    ) else (
        echo ERROR: uv not found. Install with: irm https://astral.sh/uv/install.ps1 ^| iex >&2
        exit /b 1
    )
) else (
    set UV_BIN=uv
)

%UV_BIN% run --with mcp --with fastmcp python -c "import sys; sys.path.append('.'); from core.integration.mcp_server import create_mcp_server; server = create_mcp_server('%BRAIN_DIR%'); server.run()" 2>> "%LOG_FILE%"
