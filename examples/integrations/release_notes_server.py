"""Minimal read-only MCP integration starter; install the Vittics [mcp] extra.

Run with --http for a loopback Streamable HTTP server, or no flags for stdio.
No hooks, external services, environment credentials or model calls are used.
"""
import argparse
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('Release notes example', host='127.0.0.1', port=8088,
              stateless_http=True, json_response=True)


@mcp.tool()
def release_notes(version: str) -> dict:
    """Return an example release summary. Replace the fixture with your service API."""
    return {'version': version, 'changes': ['Example documentation improvement'], 'fixture': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--http', action='store_true')
    args = parser.parse_args()
    mcp.run(transport='streamable-http' if args.http else 'stdio')
