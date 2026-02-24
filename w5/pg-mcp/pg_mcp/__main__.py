"""Module entrypoint for `python -m pg_mcp`."""

from pg_mcp.server import mcp


def main() -> None:
    """Start FastMCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

