# OptiMac MCP Server

Three-tier AI inference optimizer for Mac Mini M4 / M4 Pro. Local, edge, and cloud AI as equal peers: controls system resources, manages AI inference stacks (Ollama, LM Studio, MLX), bridges local, edge (LAN), and cloud inference via MCP, and provides intelligent model management with RAM safety checks.

## Table of Contents

- [Quick Start](#quick-start)
- [Add to Claude Desktop](#add-to-claude-desktop)
- [Add to Claude Code](#add-to-claude-code)
- [Tools (60 total)](#tools-60-total)
  - [System Monitoring (6)](#system-monitoring-6)
  - [System Control (13)](#system-control-13)
  - [AI Stack Management (7)](#ai-stack-management-7)
  - [Model Management (9)](#model-management-9)
  - [Model Tasks (9)](#model-tasks-9)
  - [Edge-to-Edge (4)](#edge-to-edge-4)
  - [Memory Pressure (2)](#memory-pressure-2)
  - [Configuration (6)](#configuration-6)
  - [Autonomy (4)](#autonomy-4)
- [Architecture](#architecture)
- [RAM Headroom Policy](#ram-headroom-policy)
- [Configuration](#configuration)
- [Requirements](#requirements)
- [License](#license)

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

## Tools (60 total)

For detailed documentation of every tool with parameters, return values, and examples, see [MCP_COMMANDS.md](../MCP_COMMANDS.md).

### System Monitoring (6)
| Tool | Description |
|------|------------|
| `optimac_memory_status` | Detailed memory stats with pressure level |
| `optimac_top_processes` | Top processes by memory or CPU |
| `optimac_disk_usage` | Disk usage for all volumes |
| `optimac_thermal_status` | CPU/GPU temps and throttling |
| `optimac_power_settings` | Current pmset configuration |
| `optimac_system_overview` | Full dashboard in one call |

### System Control (13)
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

### Model Management (9)
| Tool | Description |
|------|------------|
| `optimac_models_available` | Browse local models filtered by RAM fit |
| `optimac_ollama_available` | Ollama models filtered by RAM fit |
| `optimac_model_serve` | Load and serve a model with RAM safety check |
| `optimac_model_unload` | Unload model(s) to free RAM |
| `optimac_models_running` | Show currently loaded models across all runtimes |
| `optimac_model_dir_set` | Set model base directory |
| `optimac_model_dir_get` | Get model base directory |
| `optimac_model_ram_check` | Check if a model fits in available RAM |
| `optimac_model_chat` | Send a prompt to the loaded model |

### Model Tasks (9)
| Tool | Description |
|------|------------|
| `optimac_model_task` | Free-form local model task with file context |
| `optimac_model_code_review` | AI code review on git diffs |
| `optimac_model_generate` | Generate code from description |
| `optimac_model_edit` | Edit files with natural-language instructions |
| `optimac_model_summarize` | Summarize files |
| `optimac_model_commit` | Generate conventional commit messages |
| `optimac_cloud_escalate` | Escalate to cloud AI (OpenRouter/Anthropic/OpenAI) |
| `optimac_edge_escalate` | Escalate to edge endpoint on LAN |
| `optimac_model_route` | Smart 3-tier router: local, edge, cloud with quality gate |

### Edge-to-Edge (4)
| Tool | Description |
|------|------------|
| `optimac_edge_add` | Register a LAN/network inference endpoint |
| `optimac_edge_remove` | Remove an edge endpoint |
| `optimac_edge_list` | List all endpoints with live connectivity status |
| `optimac_edge_test` | Test inference on a specific endpoint |

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

### Autonomy (4)
| Tool | Description |
|------|------------|
| `optimac_watchdog_start` | Start background watchdog for auto-maintenance |
| `optimac_watchdog_stop` | Stop the watchdog |
| `optimac_watchdog_status` | Check watchdog state |
| `optimac_audit_log` | Read the audit log of past actions |

## Architecture

OptiMac uses a **three-tier architecture** where local, edge, and cloud AI are equal peers:

- **Local models** handle privacy-sensitive tasks, latency-critical work, and offline operation
- **Edge models** (LAN devices, other runtimes) handle cross-runtime delegation and distributed inference
- **Cloud models** handle complex reasoning, large-context tasks, and specialized capabilities
- **Smart routing** (`optimac_model_route`) tries local first, then edge endpoints by priority, then cloud
- **Streaming inference** support for both blocking and SSE modes

All local inference flows through `services/inference.ts`, edge inference through `services/inference-edge.ts`, both with error classification and auto-recovery.

## RAM Headroom Policy

Model management tools enforce a 20% headroom policy to prevent swap thrashing. A 7GB model requires 8.4GB of available RAM. Use `optimac_model_ram_check` to verify before loading, or `optimac_models_available` to see only models that fit.

## Configuration

Config file: `~/.optimac/config.json`

Created automatically on first run with sensible defaults. Shared between MCP server and GUI.

Key settings:
- `memoryWarningThreshold`: 0.75 (trigger warning at 75% used)
- `memoryCriticalThreshold`: 0.90 (trigger auto-kill at 90% used)
- `autoKillAtCritical`: true (auto-kill non-protected processes)
- `protectedProcesses`: ollama, lmstudio, python, node, claude, sshd, etc.
- `modelBaseDir`: base directory for model files (set via GUI or `optimac_model_dir_set`)
- `aiStackPorts`: ports for ollama (11434), lmstudio (1234), mlx (8080)
- `cloudEndpoints`: cloud API configs for OpenRouter, Anthropic, OpenAI (url, apiKey, defaultModel)
- `edgeEndpoints`: LAN/network inference endpoints (url, runtimeType, priority, optional apiKey)

## Requirements

- macOS 14+ (Sonoma or later)
- Node.js 18+
- Apple Silicon (M4 / M4 Pro)
- SIP disabled (for full service control) -- optional but recommended
- Passwordless sudo configured (run `sudo ./scripts/setup-sudo.sh`)

## License

MIT
