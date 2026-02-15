# OptiMac MCP Server - Command Reference

Version 2.7.0 | 89 tools across 11 domains

All tools are accessible via Claude Desktop or Claude Code when the OptiMac MCP server is configured. Each tool returns structured JSON responses.

## Table of Contents

1. [System Monitoring](#1-system-monitoring) (8 tools)
2. [System Control](#2-system-control) (15 tools)
3. [AI Stack Management](#3-ai-stack-management) (7 tools)
4. [Model Management](#4-model-management) (9 tools)
5. [Model Tasks](#5-model-tasks) (9 tools)
6. [Edge-to-Edge](#6-edge-to-edge) (4 tools)
7. [Memory Pressure](#7-memory-pressure) (2 tools)
8. [Configuration](#8-configuration) (7 tools)
9. [Autonomy](#9-autonomy) (4 tools)
10. [Security](#10-security) (7 tools)
11. [Networking](#11-networking) (8 tools)

---

## 1. System Monitoring

Read-only tools for observing system state. Safe to run at any time.

### optimac_memory_status

Get detailed memory statistics including physical RAM usage, swap, compressed memory, and pressure level.

**Parameters:** none

**Returns:** totalPhysicalMB, usedMB, freeMB, activePages, wiredPages, compressedPages, swapUsedMB, pressureLevel (nominal/warning/critical)

---

### optimac_top_processes

List top processes by memory or CPU usage.

**Parameters:**

- `sort_by` (string, optional): "memory" (default) or "cpu"
- `limit` (number, optional): Number of processes to return (default 20, max 100)
- `show_protected` (boolean, optional): Mark protected processes in output (default true)

**Returns:** Array of processes with PID, user, CPU%, MEM%, RSS in MB, and command

---

### optimac_disk_usage

Show disk usage for all mounted volumes.

**Parameters:** none

**Returns:** Array of volumes with filesystem, size, used, available (MB), and usage percentage

---

### optimac_thermal_status

Read CPU/GPU temperatures and throttling status. Requires sudo.

**Parameters:** none

**Returns:** CPU temperature (C), GPU temperature (C), throttling status

---

### optimac_power_settings

Read current pmset power management settings.

**Parameters:** none

**Returns:** Key-value map of all pmset settings

---

### optimac_system_overview

Comprehensive system health snapshot in one call. Returns memory, top 5 processes, disk, power settings, uptime, and AI stack status.

**Parameters:** none

**Returns:** Combined dashboard data from multiple sources

---

### optimac_gpu_stats

Apple Silicon GPU utilization, frequency, and memory residency statistics.

**Parameters:** none

**Returns:** gpuFrequencyMHz, activeResidency%, idleResidency%, device utilization

---

### optimac_io_stats

Disk I/O statistics using iostat — reads/writes per second and bandwidth.

**Parameters:**

- `interval` (number, optional): Sample interval in seconds (default 1)

**Returns:** Per-disk I/O rates and transfer bandwidth

---

## 2. System Control

Action tools that modify system state. Some require sudo.

### optimac_purge_memory

Force-purge inactive/purgeable memory pages. Equivalent to `sudo purge`.

**Parameters:** none

**Returns:** Memory stats before and after purge

---

### optimac_flush_dns

Flush macOS DNS cache and restart mDNSResponder.

**Parameters:** none

**Returns:** Success/failure status

---

### optimac_flush_routes

> ⚠️ **CAUTION:** This will temporarily KILL network connectivity until routes are re-established. May require reboot.

Flush the network routing table. Clears all routes including the default gateway.

**Parameters:** none

**Returns:** Success/failure status with recovery instructions

---

### optimac_set_power

Modify a single pmset power management setting.

**Parameters:**

- `setting` (string): pmset key (e.g., "sleep", "womp", "autorestart")
- `value` (number/string): Value to set

**Returns:** Confirmation of change

---

### optimac_power_optimize

Apply all recommended power settings for an always-on AI inference server. Sets sleep 0, displaysleep 0, disksleep 0, womp 1, autorestart 1, ttyskeepawake 1, powernap 0.

**Parameters:** none

**Returns:** List of settings applied

---

### optimac_power_profile

Apply named power profiles (performance, balanced, powersave) with all relevant settings in one call.

**Parameters:**

- `profile` (string): "performance", "balanced", or "powersave"

**Returns:** Applied settings

---

### optimac_kill_process

Terminate a process by PID. Protected processes cannot be killed unless force=true.

**Parameters:**

- `pid` (number): Process ID
- `force` (boolean, optional): Override protection (default false)
- `signal` (string, optional): "TERM" (default), "KILL", or "HUP"

**Returns:** Status of kill operation

---

### optimac_disable_service / optimac_enable_service

Disable or re-enable a launchd service (launch agent or daemon).

**Parameters:**

- `service` (string): Service label (e.g., "com.apple.Siri.agent")
- `domain` (string, optional): "user" (default) or "system"

---

### optimac_disable_spotlight

Disable Spotlight indexing system-wide. Highest-impact single optimization for AI inference.

**Parameters:** none

---

### optimac_rebuild_spotlight

Re-enable Spotlight and rebuild the search index.

**Parameters:** none

---

### optimac_clear_caches

Clear safe system caches, temp files, and old logs.

**Parameters:** none

**Returns:** Bytes freed, before/after disk usage

---

### optimac_set_dns

Set DNS servers for the active network interface.

**Parameters:**

- `preset` (string, optional): "cloudflare" (default), "google", "quad9", "custom"
- `servers` (string[], optional): Custom DNS servers (only with preset=custom)

---

### optimac_network_reset

> ⚠️ **CAUTION:** This will temporarily DISRUPT network connectivity.

Flush DNS, restart mDNSResponder, and optionally set fast DNS. Route flushing has been removed — use `optimac_flush_routes` separately if truly needed.

**Parameters:**

- `set_fast_dns` (boolean, optional): Also set DNS to Cloudflare 1.1.1.1 (default true)

---

### optimac_reduce_ui_overhead

Disable macOS visual effects, animations, and transparency to reduce GPU overhead for Metal-based MLX inference.

**Parameters:** none

---

### optimac_optimize_homebrew

Run Homebrew cleanup (prune 7 days) and autoremove unused dependencies.

**Parameters:** none

**Returns:** Disk space freed

---

### optimac_nvram_perf_mode

Toggle macOS performance mode via NVRAM for server-class workloads.

**Parameters:**

- `enable` (boolean): Enable or disable performance mode

---

### optimac_battery_health

Read battery health, cycle count, and power source on MacBooks.

**Parameters:** none

**Returns:** Battery percentage, health, cycle count, charging state

---

### System Utility Tools

| Tool | Description |
|------|-------------|
| `optimac_sys_eject` | Safely eject a mounted volume |
| `optimac_sys_lock` | Lock the screen |
| `optimac_sys_login_items` | List login items (startup apps) |
| `optimac_sys_restart_service` | Restart a launchd service |
| `optimac_sys_trash` | Empty the Trash |

---

## 3. AI Stack Management

Manage AI inference services: Ollama, LM Studio, MLX.

### optimac_ai_stack_status

Health check all AI inference services. Returns running status, port, loaded models, and memory usage.

**Parameters:** none

---

### optimac_ollama_start / optimac_ollama_stop

Start or stop the Ollama inference server on port 11434.

---

### optimac_ollama_models

List, pull, or remove Ollama models.

**Parameters:**

- `action` (string): "list", "pull", or "remove"
- `model` (string, optional): Model name (required for pull/remove)

---

### optimac_mlx_serve / optimac_mlx_stop

Start or stop an MLX-LM inference server.

**Parameters (serve):**

- `model` (string): HuggingFace model ID
- `port` (number, optional): Port (default 8080)

---

### optimac_mlx_quantize

Quantize an MLX model to a lower bit-width.

**Parameters:**

- `model` (string): Model identifier
- `bits` (number): Target quantization (4 or 8)
- `dry_run` (boolean, optional): Preview without executing

---

### optimac_swap_model

Intelligently swap the currently loaded model. Handles the full lifecycle: stop → purge → load → verify.

**Parameters:**

- `runtime` (string): "ollama" or "mlx"
- `model` (string): Model identifier
- `port` (number, optional): Port override

---

## 4. Model Management

Browse, serve, and manage local model files with RAM safety checks. (9 tools)

### optimac_models_available

Scan local directories for downloaded model files. Returns only models that fit in available RAM (20% headroom).

**Parameters:**

- `show_all` (boolean, optional): Show all including too-large models

---

### optimac_ollama_available

List Ollama models that are downloaded and can be served with RAM headroom.

**Parameters:**

- `show_all` (boolean, optional): Show all including too-large models

---

### optimac_model_serve

Load and serve a model. Checks RAM before loading.

**Parameters:**

- `runtime` (string): "ollama" or "mlx"
- `model` (string): Model name/path
- `force` (boolean, optional): Override RAM safety check

---

### optimac_model_unload

Unload running models to free RAM. Use "all" to stop everything.

**Parameters:**

- `runtime` (string, optional): "ollama", "mlx", or "all" (default "all")

---

### optimac_models_running

Show all models currently loaded across all runtimes.

**Parameters:** none

---

### optimac_model_dir_set / optimac_model_dir_get

Set or get the base directory where model files are stored.

**Parameters (set):**

- `path` (string): Absolute path to model directory

---

### optimac_model_ram_check

Check if a model fits in RAM with 20% headroom.

**Parameters:**

- `size_gb` (number): Model size in GB
- `model_name` (string, optional): Name for the report

---

### optimac_model_chat

Chat with a currently loaded model via OpenAI-compatible API.

**Parameters:**

- `prompt` (string): Message to send
- `system` (string, optional): System prompt
- `runtime` (string, optional): "auto", "ollama", "mlx", or "lmstudio"
- `temperature` (number, optional): Sampling temperature (default 0.3)
- `max_tokens` (number, optional): Max tokens (default 1024)

---

### optimac_model_benchmark

Benchmark a model's inference speed using Ollama HTTP API.

**Parameters:**

- `model` (string, optional): Model name (default: llama3:latest)
- `prompt` (string, optional): Benchmark prompt

**Returns:** tokens/second, time to first token, total tokens, duration

---

## 5. Model Tasks

Three-tier AI bridge: local → edge → cloud.

### optimac_model_task

Send a free-form task to the local model with file context.

**Parameters:**

- `prompt` (string): Task description
- `files` (string[], optional): Paths to include as context
- `system` (string, optional): Override system prompt

---

### optimac_model_code_review

Local AI code review on git diffs.

**Parameters:**

- `repo_path` (string): Absolute path to git repository
- `target` (string, optional): "uncommitted", "staged", or commit ref
- `focus` (string, optional): Review focus area

---

### optimac_model_generate

Generate a file from natural-language description.

**Parameters:**

- `description` (string): What to generate
- `output_path` (string): Where to write (must be inside $HOME)
- `context_files` (string[], optional): Reference files
- `language` (string, optional): Language hint

---

### optimac_model_edit

Edit existing files using natural-language instructions.

**Parameters:**

- `file_path` (string): File to edit
- `instructions` (string): What to change
- `context_files` (string[], optional): Additional context
- `create_backup` (boolean, optional): Create .bak first (default true)

**Safety:** Validates paths to prevent writes outside home directory.

---

### optimac_model_summarize

Summarize one or more files using the local model.

**Parameters:**

- `paths` (string[]): Files/directories to summarize
- `focus` (string, optional): Summary focus
- `format` (string, optional): Output format

---

### optimac_model_commit

Generate a commit message from git diff using the local model.

**Parameters:**

- `repo_path` (string): Path to git repository
- `auto_commit` (boolean, optional): Stage and commit automatically (default false)
- `files_to_stage` (string[], optional): Specific files (empty = all)
- `style` (string, optional): "conventional", "descriptive", or "short"

---

### optimac_cloud_escalate

Escalate a task to a cloud AI provider when local models can't handle it.

**Parameters:**

- `prompt` (string): Task to send
- `provider` (string, optional): "openrouter" (default), "anthropic", or "openai"
- `model` (string, optional): Specific model
- `files` (string[], optional): Files to include

---

### optimac_edge_escalate

Send a task to another inference server on the LAN.

**Parameters:**

- `prompt` (string): Task to send
- `edge_endpoint` (string): Name of configured edge endpoint
- `system` (string, optional): System prompt
- `files` (string[], optional): File paths
- `max_tokens` (number, optional): Max tokens (default 4096)

---

### optimac_model_route

Three-tier smart router: local → edge → cloud. Evaluates response quality at each tier.

**Parameters:**

- `task` (string): Task to route
- `files` (string[], optional): Context files
- `prefer` (string, optional): "local", "edge", "cloud", or "auto"
- `sensitive` (boolean, optional): Never escalate to cloud (default false)
- `output_path` (string, optional): Write result to file
- `cloud_provider` (string, optional): Fallback cloud provider
- `edge_endpoint` (string, optional): Target specific edge

---

## 6. Edge-to-Edge

Manage remote inference endpoints. Supports Ollama, MLX, LM Studio, vLLM, AnythingLLM, or any OpenAI-compatible server.

### optimac_edge_add / optimac_edge_remove / optimac_edge_list / optimac_edge_test

Register, remove, list, or test edge inference endpoints.

**Parameters (add):**

- `name` (string): Unique identifier
- `url` (string): Base URL (e.g., "http://192.168.1.50:11434")
- `runtime_type` (string, optional): "ollama", "mlx", "lmstudio", "vllm", "anythingllm", or "openai-compatible"
- `api_key` (string, optional): Authentication key
- `default_model` (string, optional): Model to request
- `priority` (number, optional): Routing priority 1-100

**Parameters (test):**

- `name` (string): Endpoint name
- `prompt` (string, optional): Custom test prompt

---

## 7. Memory Pressure

Tiered memory management tools.

### optimac_memory_pressure_check

Evaluate current memory pressure and take action if thresholds are exceeded.

**Parameters:**

- `dry_run` (boolean, optional): Report without taking action (default false)

**Returns:** Pressure level, actions taken, process list

---

### optimac_maintenance_cycle

Run a complete maintenance cycle: memory check, purge, flush DNS, check routes, clean logs, check disk, verify AI stack.

**Parameters:**

- `dry_run` (boolean, optional): Preview actions without executing (default false)

> **Note:** Route flushing has been removed from this tool. Network route health is checked read-only.

---

## 8. Configuration

Manage OptiMac settings at ~/.optimac/config.json.

### optimac_config_get / optimac_config_set

Read or modify configuration values.

**Parameters (set):**

- `key` (string): One of: memoryWarningThreshold, memoryCriticalThreshold, autoKillAtCritical, maxProcessRSSMB, maintenanceIntervalSec
- `value` (number/boolean): New value

---

### optimac_config_protect_process / optimac_config_unprotect_process

Add or remove a process from the protected list (immune to auto-kill).

**Parameters:**

- `process_name` (string): Process name or substring

---

### optimac_config_set_port

Configure the port for an AI inference service.

**Parameters:**

- `service` (string): "ollama", "lmstudio", or "mlx"
- `port` (number): Port number (1024-65535)

---

### optimac_debloat

Apply a debloat preset to disable unnecessary macOS services.

**Parameters:**

- `preset` (string): "minimal", "moderate", "aggressive", or "sequoia"

Presets (each includes previous):
- **minimal:** Siri, Notification Center, iCloud sync, analytics
- **moderate:** + Photo/media analysis, suggestions, Handoff, sharing
- **aggressive:** + Location, AirPlay, App Store updates, Apple Intelligence
- **sequoia:** + All Apple Intelligence services, ML server (macOS 15+/26+)

---

### optimac_debloat_reenable

Re-enable all services disabled by a debloat preset.

**Parameters:**

- `preset` (string): Same preset values as debloat

---

## 9. Autonomy

Background monitoring, audit logging, and system health tracking.

### optimac_watchdog_start

Start background watchdog for memory pressure and AI stack health monitoring.

**Parameters:**

- `interval_minutes` (number, optional): Check interval (default from config)

---

### optimac_watchdog_stop / optimac_watchdog_status

Stop the watchdog or get its current status.

---

### optimac_audit_read

Read the most recent entries from the audit log (~/.optimac/audit.jsonl).

**Parameters:**

- `limit` (number, optional): Entries to return (default 50, max 500)
- `tool_filter` (string, optional): Filter by tool name

---

## 10. Security

System security auditing and hardening tools.

### optimac_sec_status

Check macOS security posture: SIP, Gatekeeper, FileVault, Firewall status.

**Parameters:** none

---

### optimac_sec_firewall

Query or modify the macOS application firewall.

**Parameters:**

- `action` (string): "status", "enable", "disable", or "list"

---

### optimac_sec_audit_ports

Scan for listening network ports and flag suspicious services.

**Parameters:** none

---

### optimac_sec_audit_connections

Audit active outbound network connections for suspicious destinations.

**Parameters:** none

---

### optimac_sec_audit_unsigned

Check running processes for unsigned or ad-hoc signed binaries.

**Parameters:** none

---

### optimac_sec_audit_malware

Basic malware scan: check for known suspicious files and processes.

**Parameters:** none

---

### optimac_sec_audit_auth

Query system logs for recent authentication failures.

**Parameters:** none

**Returns:** Event count, failure count, recent failures

---

## 11. Networking

Network diagnostics, connectivity testing, and remote management.

### optimac_net_ping

Ping a host to check reachability and latency.

**Parameters:**

- `host` (string): Hostname or IP
- `count` (number, optional): Number of pings (default 4)

---

### optimac_net_connections

List active network connections and listening ports.

**Parameters:**

- `filter` (string, optional): "all" (default), "established", or "listen"
- `limit` (number, optional): Max results (default 20)

---

### optimac_net_info

Get public IP address and geolocation info.

**Parameters:** none

---

### optimac_net_speedtest

Run a quick download speed test using Cloudflare (10MB).

**Parameters:** none

---

### optimac_net_wifi

Get Wi-Fi status or toggle on/off.

**Parameters:**

- `action` (string): "status", "on", or "off"

---

### optimac_net_bluetooth

Get Bluetooth status or toggle on/off.

**Parameters:**

- `action` (string): "status", "on", or "off"

---

### optimac_net_wol

Send a Wake-on-LAN magic packet to wake a remote machine.

**Parameters:**

- `mac` (string): MAC address (e.g., "AA:BB:CC:DD:EE:FF")

---

## RAM Headroom Policy

Model management tools enforce a 20% headroom policy to prevent swap thrashing:

- 4GB model → requires 4.8GB available
- 7GB model → requires 8.4GB available
- 14GB model → requires 16.8GB available

Override with `force=true` on `optimac_model_serve` (not recommended).

## Typical Workflows

**Check what you can run:**
1. `optimac_models_available` → see all local models that fit
2. `optimac_model_ram_check size_gb=7` → check a specific size

**Load a model:**
1. `optimac_ollama_available` → see Ollama models that fit
2. `optimac_model_serve runtime=ollama model=llama3.2:3b` → serve it

**Switch models:**
1. `optimac_swap_model runtime=ollama model=qwen2.5:7b` → one-step swap

**Optimize for inference:**
1. `optimac_power_optimize` → set power for always-on
2. `optimac_reduce_ui_overhead` → free GPU resources
3. `optimac_disable_spotlight` → reduce I/O competition
4. `optimac_debloat preset=moderate` → kill background services

**Security audit:**
1. `optimac_sec_status` → check SIP, Gatekeeper, FileVault, Firewall
2. `optimac_sec_audit_ports` → scan for suspicious listeners
3. `optimac_sec_audit_unsigned` → find unsigned binaries
4. `optimac_sec_audit_auth` → recent auth failures
