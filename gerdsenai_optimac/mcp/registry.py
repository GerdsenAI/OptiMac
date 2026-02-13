"""
Server registry for tracking and managing MCP servers.

Maintains state of running servers, provides lifecycle management,
and persists state across app restarts.
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import asyncio


class ServerInfo:
    """Information about a registered MCP server."""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.pid: Optional[int] = None
        self.started_at: Optional[datetime] = None
        self.status: str = "stopped"  # stopped, starting, running, error
        self.error: Optional[str] = None
        self.request_count: int = 0
    
    def to_dict(self) -> dict:
        """Serialize to dict for persistence."""
        return {
            "name": self.name,
            "config": self.config,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "status": self.status,
            "error": self.error,
            "request_count": self.request_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ServerInfo":
        """Deserialize from dict."""
        info = cls(data["name"], data["config"])
        info.pid = data.get("pid")
        if data.get("started_at"):
            info.started_at = datetime.fromisoformat(data["started_at"])
        info.status = data.get("status", "stopped")
        info.error = data.get("error")
        info.request_count = data.get("request_count", 0)
        return info


class ServerRegistry:
    """Registry of MCP servers and their states."""
    
    def __init__(self, state_file: Optional[Path] = None):
        """Initialize registry.
        
        Args:
            state_file: Path to persist state (default: ~/.optimac/mcp_state.json)
        """
        if state_file is None:
            state_file = Path.home() / ".optimac" / "mcp_state.json"
        
        self.state_file = state_file
        self.servers: Dict[str, ServerInfo] = {}
        self._load_state()
    
    def _load_state(self):
        """Load persisted state from disk."""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file) as f:
                data = json.load(f)
            
            for server_data in data.get("servers", []):
                info = ServerInfo.from_dict(server_data)
                # Reset running servers to stopped on load
                # (they were from previous app session)
                if info.status == "running":
                    info.status = "stopped"
                    info.pid = None
                self.servers[info.name] = info
        except (json.JSONDecodeError, OSError):
            pass
    
    def _save_state(self):
        """Persist state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "servers": [info.to_dict() for info in self.servers.values()],
        }
        
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def register(self, name: str, config: dict):
        """Register a server.
        
        Args:
            name: Server name/identifier
            config: Server configuration dict
        """
        self.servers[name] = ServerInfo(name, config)
        self._save_state()
    
    async def start(self, name: str) -> bool:
        """Start a server process.
        
        Args:
            name: Server name
        
        Returns:
            True if started successfully, False otherwise.
        """
        if name not in self.servers:
            return False
        
        info = self.servers[name]
        
        # Already running
        if info.status == "running" and info.pid:
            if self._is_process_alive(info.pid):
                return True
        
        info.status = "starting"
        info.error = None
        
        try:
            # Import client to actually start server
            from gerdsenai_optimac.mcp.client import MCPClient
            
            client = MCPClient(info.config)
            success = await client.connect()
            
            if success:
                # For STDIO servers, capture PID
                if info.config["type"] == "stdio" and client._process:
                    info.pid = client._process.pid
                
                info.status = "running"
                info.started_at = datetime.now()
                self._save_state()
                return True
            else:
                info.status = "error"
                info.error = "Failed to connect"
                self._save_state()
                return False
        
        except Exception as e:
            info.status = "error"
            info.error = str(e)
            self._save_state()
            return False
    
    def stop(self, name: str) -> bool:
        """Stop a server process.
        
        Args:
            name: Server name
        
        Returns:
            True if stopped successfully, False otherwise.
        """
        if name not in self.servers:
            return False
        
        info = self.servers[name]
        
        if info.status != "running":
            return True
        
        # For STDIO servers, kill the process
        if info.config["type"] == "stdio" and info.pid:
            try:
                import os
                import signal
                os.kill(info.pid, signal.SIGTERM)
                info.pid = None
            except (ProcessLookupError, OSError):
                pass
        
        info.status = "stopped"
        self._save_state()
        return True
    
    async def restart(self, name: str) -> bool:
        """Restart a server.
        
        Args:
            name: Server name
        
        Returns:
            True if restarted successfully, False otherwise.
        """
        self.stop(name)
        await asyncio.sleep(0.5)  # Brief delay
        return await self.start(name)
    
    def get_status(self, name: str) -> Optional[dict]:
        """Get server health status.
        
        Args:
            name: Server name
        
        Returns:
            Status dict:
            {
                "name": str,
                "status": str,
                "pid": int | None,
                "uptime_seconds": int | None,
                "request_count": int,
                "error": str | None,
            }
        """
        if name not in self.servers:
            return None
        
        info = self.servers[name]
        
        uptime = None
        if info.started_at and info.status == "running":
            uptime = int((datetime.now() - info.started_at).total_seconds())
        
        return {
            "name": info.name,
            "status": info.status,
            "pid": info.pid,
            "uptime_seconds": uptime,
            "request_count": info.request_count,
            "error": info.error,
        }
    
    def list_all(self) -> List[dict]:
        """List all registered servers.
        
        Returns:
            List of server status dicts.
        """
        return [
            self.get_status(name)
            for name in self.servers
        ]
    
    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process is still running.
        
        Args:
            pid: Process ID
        
        Returns:
            True if process exists, False otherwise.
        """
        try:
            import os
            import signal
            # Send signal 0 (no-op) to check if process exists
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False
    
    def increment_request_count(self, name: str):
        """Increment request counter for a server.
        
        Args:
            name: Server name
        """
        if name in self.servers:
            self.servers[name].request_count += 1
            self._save_state()
