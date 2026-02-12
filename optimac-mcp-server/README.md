# OptiMac MCP Server

System-level AI inference optimizer for Mac Mini M4 / M4 Pro. Controls memory, power, network, processes, and AI stacks (Ollama, LM Studio, MLX) via MCP -- giving Claude full admin control over your machine's performance.

## Quick Start

```bash
cd optimac-mcp-server
chmod +x scripts/install.sh scripts/setup-sudo.sh
./scripts/install.sh
sudo ./scripts/setup-sudo.sh
```

## Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "optimac": {
      "command": "node",
      "args": ["/path/to/optimac-mcp-server/dist/index.js"]
    }
  }
}
```

## Add to Claude Code

```bash
claude mcp add optimac node /path/to/optimac-mcp-server/dist/index.js
```

## Tools (32 total)

### System Monitoring (6)
| Tool | Description |
|------|------------|
| `optimac_memory_status` | Detailed memory stats with pressure level |
| `optimac_top_processes` | Top processes by memory or CPU |
| `optimac_disk_usage` | Disk usage for all volumes |
| `optimac_thermal_status` | CPU/GPU temps and throttling |
| `optimac_power_settings` | Current pmset configuration |
| `optimac_system_overview` | Full dashboard in one call |

### System Control (11)
| Tool | Description |
|------|------------|
| `optimac_purge_memory` | Force-purge inactive pages |
| `optimac_flush_dns` | Flush DNS cache |
| `optimac_flush_routes` | Flush network routing table |
| `optimac_set_power` | Modify individual pmset setting |
| `optimac_power_optimize` | Apply all AI server power settings |
| `optimac_kill_process` | Kill process with protection check |
| `optimac_disable_service` | Disable launchd service |
| `optimac_enable_service` | Re-enable launchd service |
| `optimac_disable_spotlight` | Disable Spotlight indexing |
| `optimac_clear_caches` | Clear temp files and old logs |
| `optimac_set_dns` | Set DNS servers (presets available) |
| `optimac_network_reset` | Full network stack reset |
| `optimac_reduce_ui_overhead` | Disable animations and transparency |

### AI Stack Management (7)
| Tool | Description |
|------|------------|
| `optimac_ai_stack_status` | Health check all AI services |
| `optimac_ollama_start` | Start Ollama server |
| `optimac_ollama_stop` | Stop Ollama server |
| `optimac_ollama_models` | List/pull/remove Ollama models |
| `optimac_mlx_serve` | Start MLX-LM server for a model |
| `optimac_mlx_stop` | Stop MLX-LM server |
| `optimac_swap_model` | Smart model swap (stop, purge, restart) |

### Memory Pressure (2)
| Tool | Description |
|------|------------|
| `optimac_memory_pressure_check` | Tiered pressure response |
| `optimac_maintenance_cycle` | Full 8-step maintenance cycle |

### Configuration (6)
| Tool | Description |
|------|------------|
| `optimac_config_get` | Read current configuration |
| `optimac_config_set` | Modify a config value |
| `optimac_config_protect_process` | Add to protected process list |
| `optimac_config_unprotect_process` | Remove from protected list |
| `optimac_config_set_port` | Set AI service port |
| `optimac_debloat` | Apply debloat preset (minimal/moderate/aggressive) |

## Configuration

Config file: `~/.optimac/config.json`

Created automatically on first run with sensible defaults for a 16GB M4.

Key settings:
- `memoryWarningThreshold`: 0.75 (trigger warning at 75% used)
- `memoryCriticalThreshold`: 0.90 (trigger auto-kill at 90% used)
- `autoKillAtCritical`: true (auto-kill non-protected processes)
- `protectedProcesses`: ollama, lmstudio, python, node, claude, sshd, etc.

## Requirements

- macOS 14+ (Sonoma or later)
- Node.js 18+
- Apple Silicon (M4 / M4 Pro)
- SIP disabled (for full service control) -- optional but recommended
- Passwordless sudo configured (run `sudo ./scripts/setup-sudo.sh`)

## License

MIT
