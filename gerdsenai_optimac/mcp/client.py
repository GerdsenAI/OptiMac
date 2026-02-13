"""
MCP protocol client for communicating with MCP servers.

Supports both STDIO and HTTP server types.
Enables tool execution and resource access.
"""

import asyncio
import json
from typing import List, Dict, Optional, Any


class MCPClient:
    """MCP protocol client for tool execution & resource access."""

    def __init__(self, server_config: dict):
        """Initialize client from server config.

        Args:
            server_config: Normalized server config from discovery
        """
        self.config = server_config
        self.name = server_config["name"]
        self.server_type = server_config["type"]

        # Connection state
        self._connected = False
        self._process = None  # For STDIO
        self._session = None  # For HTTP

        # Cached server info
        self._tools = None
        self._resources = None

    async def connect(self) -> bool:
        """Establish connection to MCP server.

        Returns:
            True if connected successfully, False otherwise.
        """
        if self._connected:
            return True

        try:
            if self.server_type == "stdio":
                return await self._connect_stdio()
            elif self.server_type == "http":
                return await self._connect_http()
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def _connect_stdio(self) -> bool:
        """Connect to STDIO MCP server by starting subprocess."""
        import subprocess

        cmd = self.config["command"]
        args = self.config.get("args", [])
        env = self.config.get("env", {})

        # Build environment (merge with current)
        import os

        full_env = os.environ.copy()
        full_env.update(env)

        # Start server process
        self._process = await asyncio.create_subprocess_exec(
            cmd,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

        # Send initialization request
        init_response = await self._send_jsonrpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "OptiMac",
                    "version": "1.0.0",
                },
            },
        )

        if init_response and "result" in init_response:
            self._connected = True
            return True

        return False

    async def _connect_http(self) -> bool:
        """Connect to HTTP MCP server."""
        import aiohttp

        # Create session with auth if needed
        headers = {}
        auth_config = self.config.get("auth")

        if auth_config:
            auth_type = auth_config.get("type")
            if auth_type == "bearer":
                token = auth_config.get("token")
                headers["Authorization"] = f"Bearer {token}"

        self._session = aiohttp.ClientSession(headers=headers)

        # Test connection with ping
        try:
            async with self._session.get(
                f"{self.config['url']}/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    self._connected = True
                    return True
        except Exception:
            pass

        return False

    async def _send_jsonrpc(self, method: str, params: dict) -> Optional[dict]:
        """Send JSON-RPC request to STDIO server.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Response dict or None on error.
        """
        if not self._process:
            return None

        # Build request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        # Send request
        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str.encode())
        await self._process.stdin.drain()

        # Read response
        response_line = await self._process.stdout.readline()
        if not response_line:
            return None

        try:
            return json.loads(response_line.decode())
        except json.JSONDecodeError:
            return None

    async def list_tools(self) -> List[Dict]:
        """Get available tools from server.

        Returns:
            List of tool definitions:
            [
                {
                    "name": "tool_name",
                    "description": "...",
                    "inputSchema": {...},
                },
                ...
            ]
        """
        if self._tools is not None:
            return self._tools

        if not self._connected:
            await self.connect()

        if self.server_type == "stdio":
            response = await self._send_jsonrpc("tools/list", {})
            if response and "result" in response:
                self._tools = response["result"].get("tools", [])
                return self._tools
        elif self.server_type == "http":
            # HTTP implementation
            async with self._session.get(f"{self.config['url']}/tools") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._tools = data.get("tools", [])
                    return self._tools

        return []

    async def list_resources(self) -> List[Dict]:
        """Get available resources from server.

        Returns:
            List of resource definitions:
            [
                {
                    "uri": "resource_uri",
                    "name": "...",
                    "description": "...",
                },
                ...
            ]
        """
        if self._resources is not None:
            return self._resources

        if not self._connected:
            await self.connect()

        if self.server_type == "stdio":
            response = await self._send_jsonrpc("resources/list", {})
            if response and "result" in response:
                self._resources = response["result"].get("resources", [])
                return self._resources
        elif self.server_type == "http":
            async with self._session.get(f"{self.config['url']}/resources") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._resources = data.get("resources", [])
                    return self._resources

        return []

    async def execute_tool(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """Execute a tool with given arguments.

        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments as dict

        Returns:
            Tool result:
            {
                "content": [...],  # Tool output
                "isError": bool,
            }
        """
        if not self._connected:
            await self.connect()

        if self.server_type == "stdio":
            response = await self._send_jsonrpc(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments,
                },
            )
            if response and "result" in response:
                return response["result"]
            elif response and "error" in response:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": response["error"].get("message", "Unknown error"),
                        }
                    ],
                    "isError": True,
                }
        elif self.server_type == "http":
            async with self._session.post(
                f"{self.config['url']}/tools/call",
                json={"name": tool_name, "arguments": arguments},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {
                        "content": [{"type": "text", "text": f"HTTP {resp.status}"}],
                        "isError": True,
                    }

        return {
            "content": [{"type": "text", "text": "Not connected"}],
            "isError": True,
        }

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI.

        Args:
            uri: Resource URI to read

        Returns:
            Resource content as string.
        """
        if not self._connected:
            await self.connect()

        if self.server_type == "stdio":
            response = await self._send_jsonrpc(
                "resources/read",
                {"uri": uri},
            )
            if response and "result" in response:
                contents = response["result"].get("contents", [])
                if contents:
                    return contents[0].get("text", "")
        elif self.server_type == "http":
            async with self._session.get(
                f"{self.config['url']}/resources/read",
                params={"uri": uri},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    contents = data.get("contents", [])
                    if contents:
                        return contents[0].get("text", "")

        return ""

    async def disconnect(self):
        """Close connection."""
        if self.server_type == "stdio" and self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
        elif self.server_type == "http" and self._session:
            await self._session.close()
            self._session = None

        self._connected = False
