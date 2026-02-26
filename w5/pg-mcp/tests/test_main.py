"""Tests for module entrypoint transport selection."""

from unittest.mock import Mock


def test_main_uses_stdio_transport(monkeypatch) -> None:
    """Entrypoint should keep stdio behavior by default."""
    import pg_mcp.__main__ as main_module
    from pg_mcp.config.settings import Settings

    settings = Settings(_env_file=None, deepseek={"api_key": "sk-test"})
    bind_lifespan = Mock()
    force_utf8 = Mock()
    configure_logging = Mock()
    run = Mock()

    monkeypatch.setattr(main_module, "Settings", lambda: settings)
    monkeypatch.setattr(main_module, "_bind_lifespan", bind_lifespan)
    monkeypatch.setattr(main_module, "_force_utf8_stdio", force_utf8)
    monkeypatch.setattr(main_module, "configure_logging", configure_logging)
    monkeypatch.setattr(main_module.mcp, "run", run)

    main_module.main()

    bind_lifespan.assert_called_once_with()
    force_utf8.assert_called_once_with()
    configure_logging.assert_called_once_with("INFO")
    run.assert_called_once_with(transport="stdio", show_banner=False)


def test_main_uses_streamable_http_transport(monkeypatch) -> None:
    """Entrypoint should pass streamable-http endpoint options to FastMCP."""
    import pg_mcp.__main__ as main_module
    from pg_mcp.config.settings import Settings

    settings = Settings(
        _env_file=None,
        deepseek={"api_key": "sk-test"},
        server={
            "transport": "streamable-http",
            "host": "0.0.0.0",
            "port": 19000,
            "path": "/gateway/mcp",
            "stateless_http": True,
            "show_banner": False,
        },
    )
    bind_lifespan = Mock()
    force_utf8 = Mock()
    configure_logging = Mock()
    run = Mock()

    monkeypatch.setattr(main_module, "Settings", lambda: settings)
    monkeypatch.setattr(main_module, "_bind_lifespan", bind_lifespan)
    monkeypatch.setattr(main_module, "_force_utf8_stdio", force_utf8)
    monkeypatch.setattr(main_module, "configure_logging", configure_logging)
    monkeypatch.setattr(main_module.mcp, "run", run)

    main_module.main()

    bind_lifespan.assert_called_once_with()
    force_utf8.assert_not_called()
    configure_logging.assert_called_once_with("INFO")
    run.assert_called_once_with(
        transport="streamable-http",
        show_banner=False,
        host="0.0.0.0",
        port=19000,
        path="/gateway/mcp",
        stateless_http=True,
    )
