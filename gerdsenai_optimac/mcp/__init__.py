"""
MCP (Model Context Protocol) integration for OptiMac.

Provides native macOS menu bar control for MCP servers:
- Server discovery from config files
- Start/stop/restart server processes
- Tool execution with dynamic input dialogs
- Resource browsing
- Health monitoring

This makes OptiMac the only macOS app with native MCP control.
"""

from gerdsenai_optimac.mcp.discovery import discover_servers
from gerdsenai_optimac.mcp.client import MCPClient
from gerdsenai_optimac.mcp.registry import ServerRegistry

__all__ = ["discover_servers", "MCPClient", "ServerRegistry"]
