"""
MCP server discovery from config files.

Scans multiple config sources to find user's MCP servers:
- ~/.config/anthropic/config.json (Anthropic SDK)
- ~/Library/Application Support/Claude/claude_desktop_config.json
- ~/.optimac/mcp_servers.json (custom)
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


def get_user_mcp_configs() -> List[Path]:
    """Get list of potential MCP config file paths.

    Returns:
        List of config file paths (may not all exist).
    """
    home = Path.home()
    return [
        # Anthropic SDK default
        home / ".config" / "anthropic" / "config.json",
        # Claude Desktop
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json",
        # OptiMac custom
        home / ".optimac" / "mcp_servers.json",
    ]


def parse_server_config(name: str, config: dict) -> Optional[Dict]:
    """Parse a server config into normalized format.

    Args:
        name: Server name/identifier
        config: Raw config dict from file

    Returns:
        Normalized server info dict or None if invalid:
        {
            "name": str,
            "type": "stdio" | "http",
            "command": str,  # for STDIO
            "args": list[str],  # for STDIO
            "url": str,  # for HTTP
            "auth": dict,  # optional
            "env": dict,  # optional environment variables
        }
    """
    if not config:
        return None

    # Detect server type
    if "command" in config:
        # STDIO server
        return {
            "name": name,
            "type": "stdio",
            "command": config["command"],
            "args": config.get("args", []),
            "env": config.get("env", {}),
        }
    elif "url" in config:
        # HTTP server
        server_info = {
            "name": name,
            "type": "http",
            "url": config["url"],
        }

        # Parse authentication if present
        if "auth" in config:
            server_info["auth"] = config["auth"]

        return server_info

    return None


def discover_servers() -> List[Dict]:
    """Discover all MCP servers from config files.

    Returns:
        List of normalized server configs.
    """
    servers = []

    for config_path in get_user_mcp_configs():
        if not config_path.exists():
            continue

        try:
            with open(config_path) as f:
                config_data = json.load(f)

            # Handle different config formats
            if "mcpServers" in config_data:
                # Claude Desktop format
                mcp_servers = config_data["mcpServers"]
            elif "servers" in config_data:
                # Generic format
                mcp_servers = config_data["servers"]
            else:
                # Assume root is servers dict
                mcp_servers = config_data

            # Parse each server
            for name, server_config in mcp_servers.items():
                parsed = parse_server_config(name, server_config)
                if parsed:
                    parsed["source"] = str(config_path)
                    servers.append(parsed)

        except (json.JSONDecodeError, OSError) as e:
            # Skip invalid configs
            print(f"Warning: Failed to parse {config_path}: {e}")
            continue

    return servers


def get_server_by_name(name: str) -> Optional[Dict]:
    """Get a specific server config by name.

    Args:
        name: Server name to find

    Returns:
        Server config dict or None if not found.
    """
    servers = discover_servers()
    for server in servers:
        if server["name"] == name:
            return server
    return None
