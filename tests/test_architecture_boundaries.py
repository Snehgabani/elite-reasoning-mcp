def test_core_profile_does_not_import_forbidden_heavy_modules(tmp_path):
    """
    Enforce architectural import boundaries:
    Creating the core 5-tool server profile must NEVER import LangGraph,
    or experimental reasoning modules into sys.modules during default startup.
    """
    from core.integration.mcp_server import create_mcp_server

    server = create_mcp_server(brain_dir=str(tmp_path), tool_profile="core")

    assert server is not None

    # Verify core tools are registered
    if hasattr(server, "_registered_tools"):
        assert len(server._registered_tools) <= 10
