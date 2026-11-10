"""Explicitly configured tool adapters. MCP servers are trusted company integrations."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from datetime import timedelta
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from .tools import INTEGRATION_SPECS, MAX_OUTPUT, command_environment, ToolError


class Integrations:
    def __init__(self, settings):
        self.s = settings

    def allowed(self, role, name):
        cfg = self.s.raw.get('tools') or {}
        if name == 'browser_journey':
            browser = cfg.get('browser') or {}
            return browser.get('enabled') is True and role in (browser.get('roles') or [])
        if name in ('mcp_call', 'mcp_list_tools'):
            return any(c.get('enabled', True) is True and role in (c.get('roles') or []) and c.get('tools')
                       for c in (cfg.get('mcp') or {}).values())
        return False

    def names(self, role):
        return [n for n in INTEGRATION_SPECS if self.allowed(role, n)]

    def schema(self, role, name):
        schema = {'name': name, **copy.deepcopy(INTEGRATION_SPECS[name])}
        config = self.s.raw.get('tools') or {}
        if name.startswith('mcp_'):
            servers = [n for n, c in (config.get('mcp') or {}).items()
                       if c.get('enabled', True) is True and role in (c.get('roles') or []) and c.get('tools')]
            schema['input_schema']['properties']['server']['enum'] = servers
        else:
            origins = (config.get('browser') or {}).get('allowed_origins') or ['loopback development servers']
            schema['description'] += ' Allowed destinations: ' + ', '.join(origins) + '.'
        return schema

    def call(self, role, name, args, ws):
        if not self.allowed(role, name):
            raise ToolError('This integration is not enabled for your role.')
        if not ws:
            raise ToolError('Integration tools require a project workspace.')
        if name == 'browser_journey':
            from .browser import journey
            return journey(ws, (self.s.raw.get('tools') or {}).get('browser') or {}, args)
        config = ((self.s.raw.get('tools') or {}).get('mcp') or {}).get(args.get('server'))
        if not config or config.get('enabled', True) is not True or role not in (config.get('roles') or []):
            raise ToolError('MCP server is not permitted for your role.')
        if name == 'mcp_call' and args.get('tool') not in (config.get('tools') or []):
            raise ToolError('MCP tool is not on the company allowlist.')
        try:
            return asyncio.run(asyncio.wait_for(self._mcp(config, name, args, ws),
                                                timeout=min(120, self.s.command_timeout)))
        except ImportError as exc:
            raise ToolError('MCP support needs pip install -e ".[mcp]".') from exc
        except ToolError:
            raise
        except Exception as exc:
            # A server exception can contain credential values; never relay it to an agent.
            raise ToolError(f'MCP operation failed ({type(exc).__name__}); check the configured server.') from exc

    def inventory(self):
        """Configuration metadata only; never return endpoint URLs, headers or secret values."""
        return [{'name': name, 'transport': c.get('transport', 'stdio'),
                 'enabled': c.get('enabled', True) is True,
                 'roles': c.get('roles') or [], 'tools': c.get('tools') or [],
                 'missing_credentials': sorted({v for v in (c.get('headers_env') or {}).values()
                                                if isinstance(v, str) and not os.environ.get(v)})}
                for name, c in sorted(((self.s.raw.get('tools') or {}).get('mcp') or {}).items())]

    @asynccontextmanager
    async def _transport(self, config, ws):
        from mcp import StdioServerParameters
        transport = config.get('transport', 'stdio')
        if transport == 'streamable_http':
            import httpx
            from mcp.client.streamable_http import streamable_http_client
            url = config.get('url', '')
            parsed = urlsplit(url)
            if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or not (parsed.scheme == 'https' or parsed.scheme == 'http'
                            and parsed.hostname in ('127.0.0.1', 'localhost', '::1'))):
                raise ToolError('Remote MCP needs HTTPS (HTTP only on loopback), without URL credentials or query strings.')
            headers = {}
            for header, variable in (config.get('headers_env') or {}).items():
                if (not isinstance(header, str) or not re.fullmatch(r'[A-Za-z0-9-]+', header)
                        or header.lower() in ('host', 'content-length', 'connection')
                        or not isinstance(variable, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', variable)):
                    raise ToolError('MCP headers_env needs safe header names bound to environment variable names.')
                value = os.environ.get(variable)
                if not value or '\r' in value or '\n' in value:
                    raise ToolError('A configured MCP credential is missing or invalid.')
                headers[header] = value
            async def refuse_redirect(response):
                # The SDK implements its own same-origin redirect handling;
                # response hooks run before it can reissue the request.
                if response.is_redirect:
                    raise ToolError('Remote MCP redirects are not permitted; configure the final endpoint explicitly.')
            async with httpx.AsyncClient(headers=headers, follow_redirects=False, trust_env=False,
                                         event_hooks={'response': [refuse_redirect]},
                                         timeout=httpx.Timeout(30, read=60)) as client:
                async with streamable_http_client(url, http_client=client) as streams:
                    yield streams[0], streams[1]
        elif transport == 'stdio':
            from mcp.client.stdio import stdio_client
            command = config.get('command')
            if not isinstance(command, str) or not command:
                raise ToolError('MCP server needs a trusted command in org.yaml.')
            environment = command_environment()
            for var in config.get('env_names') or []:
                if not isinstance(var, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', var):
                    raise ToolError('MCP env_names must be environment variable names.')
                if var in os.environ:
                    environment[var] = os.environ[var]
            params = StdioServerParameters(command=command, args=config.get('args') or [],
                                           cwd=str(ws.root), env=environment)
            with open(os.devnull, 'w') as errlog:
                async with stdio_client(params, errlog=errlog) as streams:
                    yield streams
        else:
            raise ToolError('MCP transport must be stdio or streamable_http.')

    async def _mcp(self, config, name, args, ws):
        from mcp import ClientSession
        async with self._transport(config, ws) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=60)) as session:
                await session.initialize()
                available, cursor, seen = [], None, set()
                while True:
                    response = await session.list_tools(cursor=cursor)
                    available.extend(response.tools)
                    cursor = response.nextCursor
                    if not cursor:
                        break
                    if cursor in seen or len(available) > 1000:
                        raise ToolError('MCP tool listing exceeded company limits.')
                    seen.add(cursor)
                allowed = {t.name: t for t in available if t.name in (config.get('tools') or [])}
                if name == 'mcp_list_tools':
                    return json.dumps([{'name': t.name, 'description': t.description,
                                        'input_schema': t.inputSchema} for t in allowed.values()])[:MAX_OUTPUT]
                if args['tool'] not in allowed:
                    raise ToolError('MCP server did not advertise the requested tool.')
                response = await session.call_tool(args['tool'], arguments=args.get('arguments') or {})
                if response.isError:
                    raise ToolError('The MCP server reported a tool failure.')
                return json.dumps(response.model_dump(mode='json'))[:MAX_OUTPUT]
