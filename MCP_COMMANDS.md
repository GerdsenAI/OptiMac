# OptiMac MCP Server - Command Reference

Version 1.3.0 | 55 tools across 8 domains

All tools are accessible via Claude Desktop or Claude Code when the OptiMac MCP server is configured. Each tool returns structured JSON responses.

## Table of Contents

1. System Monitoring (6 tools)
2. System Control (13 tools)
3. AI Stack Management (7 tools)
4. Model Management (9 tools)
5. Model Tasks (8 tools)
6. Memory Pressure (2 tools)
7. Configuration (6 tools)
8. Autonomy (4 tools)

---

## 1. System Monitoring

Read-only tools for observing system state. Safe to run at any time.

### optimac_memory_status

Get detailed memory statistics including physical RAM usage, swap, compressed memory, and pressure level.

**Parameters:** none

**Returns:** totalPhysicalMB, usedMB, freeMB, activePages, wiredPages, compressedPages, swapUsedMB, pressureLevel (nominal/warning/critical)

**Example use:** "How much RAM am I using right now?"

---

### optimac_top_processes

List top processes by memory or CPU usage.

**Parameters:**
- `sort_by` (string, optional): "memory" (default) or "cpu"
- `limit` (number, optional): Number of processes to return (default 20, max 100)
- `show_protected` (boolean, optional): Mark protected processes in output (default true)

**Returns:** Array of processes with PID, user, CPU%, MEM%, RSS in MB, and command

**Example use:** "What's eating all my RAM?"

---

### optimac_disk_usage

Show disk usage for all mounted volumes.

**Parameters:** none

**Returns:** Array of volumes with filesystem, size, used, available (MB), and usage percentage

**Example use:** "How much disk space do I have left?"

---

### optimac_thermal_status

Read CPU/GPU temperatures and throttling status. Requires sudo.

**Parameters:** none

**Returns:** CPU temperature (C), GPU temperature (C), throttling status

**Example use:** "Is my Mac overheating during inference?"

---

### optimac_power_settings

Read current pmset power management settings.

**Parameters:** none

**Returns:** Key-value map of all pmset settings

**Example use:** "What are my current power settings?"

---

### optimac_system_overview

Comprehensive system health snapshot in one call. Returns memory, top 5 processes, disk, power settings, uptime, and AI stack status.

**Parameters:** none

**Returns:** Combined dashboard data from multiple sources

**Example use:** "Give me a full system health check"

---

## 2. System Control

Action tools that modify system state. Some require sudo.

### optimac_purge_memory

Force-purge inactive/purgeable memory pages. Equivalent to `sudo purge`.

**Parameters:** none

**Returns:** Memory stats before and after purge

**Example use:** "Free up RAM after unloading a model"

---

### optimac_flush_dns

Flush macOS DNS cache and restart mDNSResponder.

**Parameters:** none

**Returns:** Success/failure status

**Example use:** "I'm getting DNS errors when pulling models"

---

### optimac_flush_routes

Flush the network routing table. Clears stale routes.

**Parameters:** none

**Returns:** Success/failure status

---

### optimac_set_power

Modify a single pmset power management setting.

**Parameters:**
- `setting` (string): pmset key (e.g., "sleep", "womp", "autorestart")
- `value` (number/string): Value to set

**Returns:** Confirmation of change

---

### optimac_power_optimize

Apply all recommended power settings for an always-on AI inference server in a single call. Sets sleep 0, displaysleep 0, disksleep 0, womp 1, autorestart 1, ttyskeepawake 1, powernap 0.

**Parameters:** none

**Returns:** List of settings applied

**Example use:** "Configure this Mac as a 24/7 inference server"

---

### optimac_kill_process

Terminate a process by PID. Protected processes (Ollama, LM Studio, MLX, sshd, etc.) cannot be killed unless force=true.

**Parameters:**
- `pid` (number): Process ID
- `force` (boolean, optional): Override protection (default false)
- `signal` (string, optional): Signal to send - "TERM" (default), "KILL", or "HUP"

**Returns:** Status of kill operation

---

### optimac_disable_service

Disable a launchd service (launch agent or daemon).

**Parameters:**
- `service` (string): Service label (e.g., "com.apple.Siri.agent")
- `domain` (string, optional): "user" (default) or "system"

**Returns:** Confirmation of disable

---

### optimac_enable_service

Re-enable a previously disabled launchd service.

**Parameters:**
- `service` (string): Service label
- `domain` (string, optional): "user" (default) or "system"

**Returns:** Confirmation of enable

---

### optimac_disable_spotlight

Disable Spotlight indexing system-wide. Highest-impact single optimization for AI inference.

**Parameters:** none

**Returns:** Confirmation

**Example use:** "Stop Spotlight from competing with model I/O"

---

### optimac_clear_caches

Clear safe system caches, temp files, and old logs.

**Parameters:** none

**Returns:** Bytes freed

---

### optimac_set_dns

Set DNS servers for the active network interface.

**Parameters:**
- `preset` (string, optional): "cloudflare" (default), "google", "quad9", "custom"
- `servers` (string[], optional): Custom DNS servers (only with preset=custom)

**Returns:** Confirmation of DNS change

---

### optimac_network_reset

Full network stack reset: flush DNS, flush routes, reset mDNSResponder, optionally set fast DNS.

**Parameters:**
- `set_fast_dns` (boolean, optional): Also set DNS to Cloudflare 1.1.1.1 (default true)

**Returns:** Summary of reset steps

---

### optimac_reduce_ui_overhead

Disable macOS visual effects, animations, and transparency to reduce GPU overhead for Metal-based MLX inference.

**Parameters:** none

**Returns:** List of settings changed

---

## 3. AI Stack Management

Manage AI inference services: Ollama, LM Studio, MLX.

### optimac_ai_stack_status

Health check all AI inference services. Returns running status, port, loaded models, and memory usage for each service.

**Parameters:** none

**Returns:** Status object for ollama, lmstudio, mlx_server, openclaw, claude_code

**Example use:** "Which AI services are running right now?"

---

### optimac_ollama_start

Start the Ollama inference server on port 11434.

**Parameters:** none

**Returns:** Status (already_running, started, failed, or not_installed)

---

### optimac_ollama_stop

Stop the Ollama inference server.

**Parameters:** none

**Returns:** Status (stopped or still_running)

---

### optimac_ollama_models

List, pull, or remove Ollama models.

**Parameters:**
- `action` (string): "list", "pull", or "remove"
- `model` (string, optional): Model name (required for pull/remove, e.g., "llama3.2:3b")

**Returns:** Model list, pull progress, or removal confirmation

---

### optimac_mlx_serve

Start an MLX-LM inference server for a specific model.

**Parameters:**
- `model` (string): HuggingFace model ID (e.g., "mlx-community/Qwen2.5-7B-Instruct-4bit")
- `port` (number, optional): Port to serve on (default 8080)

**Returns:** Status with API endpoint URL

---

### optimac_mlx_stop

Stop any running mlx_lm.server processes.

**Parameters:** none

**Returns:** Confirmation

---

### optimac_swap_model

Intelligently swap the currently loaded model for a different one. Handles the full lifecycle: stop existing servers, purge memory, start new model.

**Parameters:**
- `runtime` (string): "ollama" or "mlx"
- `model` (string): Model identifier
- `port` (number, optional): Port override

**Returns:** Step-by-step status of the swap operation

**Example use:** "Switch from Llama 3.2 to Qwen 2.5 on Ollama"

---

## 4. Model Management

Browse, serve, and manage local model files with RAM safety checks. (9 tools)

### optimac_models_available

Scan the model base directory and common model locations for downloaded model files. Returns only models that fit in currently available RAM (with ~20% headroom).

Scans for .gguf, .safetensors, .bin, .pth, .pt, .onnx files larger than 50MB.

Search locations: modelBaseDir (from config), ~/.ollama/models, ~/.cache/huggingface/hub, ~/.cache/lm-studio/models, ~/models.

**Parameters:**
- `show_all` (boolean, optional): Show all models including those too large for current RAM (default false)

**Returns:**
- systemRAM: total/used/available in GB
- headroomPolicy: explanation of 20% reservation
- searchedDirectories: paths scanned
- models: array of model files with path, size, fitsInRAM, requiredRAM_GB

**Example use:** "What models can I run right now?"

---

### optimac_ollama_available

List Ollama models that are downloaded and can be served. Only returns models that fit in currently available RAM with 20% headroom. Also shows currently running models.

**Parameters:**
- `show_all` (boolean, optional): Show all including too-large models (default false)

**Returns:**
- availableRAM_GB, totalInstalled, canRunNow, tooLargeForRAM counts
- models: array with name, id, sizeGB, fitsInRAM, requiredRAM_GB
- currentlyRunning: output of `ollama ps`

**Example use:** "Which of my Ollama models can I load without swapping?"

---

### optimac_model_serve

Load and serve a model for inference. Checks RAM availability before loading and refuses models that would exceed available RAM with 20% headroom.

**Parameters:**
- `runtime` (string): "ollama" or "mlx"
- `model` (string): Model name (Ollama tag) or path/HuggingFace ID (MLX)
- `force` (boolean, optional): Override RAM safety check (default false)

**Returns:**
- On success: status, runtime, model, port, API endpoint
- On too-large: error with modelSizeGB, requiredGB, availableGB, suggestions

**Example use:** "Serve llama3.2:3b with Ollama" or "Start MLX with mlx-community/Qwen2.5-7B-Instruct-4bit"

**Safety:** Will return MODEL_TOO_LARGE error if model + 20% headroom exceeds available RAM. Use force=true to override (may cause swap thrashing).

---

### optimac_model_unload

Unload a running model to free RAM. For Ollama, unloads model from memory (keeps it downloaded). For MLX, stops the server process. Use "all" to stop everything.

**Parameters:**
- `runtime` (string, optional): "ollama", "mlx", or "all" (default "all")

**Returns:** Unload status per service, RAM after unload, next step suggestion

**Example use:** "Unload all models to free RAM"

---

### optimac_models_running

Show all models currently loaded and serving across all runtimes (Ollama, MLX, LM Studio).

**Parameters:** none

**Returns:** Running status for each runtime with loaded models, ports, and current RAM usage

**Example use:** "What models are loaded right now?"

---

### optimac_model_dir_set

Set the base directory where model files are stored. This directory is scanned by optimac_models_available.

**Parameters:**
- `path` (string): Absolute path to the model directory

**Returns:** Confirmation with path

**Example use:** `optimac_model_dir_set path="/Volumes/M2 Raid0/AI Models"`

---

### optimac_model_dir_get

Get the currently configured model base directory.

**Parameters:** none

**Returns:** Current modelBaseDir path and whether it exists

---

### optimac_model_ram_check

Check if a specific model can be loaded without causing swap thrashing. Takes model size in GB and checks against available RAM with 20% headroom.

**Parameters:**
- `size_gb` (number): Model size in GB (e.g., 4.7)
- `model_name` (string, optional): Model name for the report

**Returns:**
- fits: boolean verdict
- modelSizeGB, requiredWithHeadroomGB, availableRAM_GB
- headroomAfterLoadGB (if fits)
- suggestions (if doesn't fit)

**Example use:** "Can I load a 7GB model right now?"

---

### optimac_model_chat

Send a prompt to a currently loaded model and get a response. Uses the OpenAI-compatible /v1/chat/completions endpoint exposed by Ollama, MLX, or LM Studio.

Automatically detects which runtime has a model loaded. If multiple are running, specify the runtime parameter.

**Parameters:**
- `prompt` (string): The message to send to the model
- `system` (string, optional): System prompt for context
- `runtime` (string, optional): "auto" (default), "ollama", "mlx", or "lmstudio"
- `temperature` (number, optional): Sampling temperature (default 0.3)
- `max_tokens` (number, optional): Max tokens to generate (default 1024)

**Returns:**
- runtime, model, port
- response: The model's text response
- usage: prompt_tokens, completion_tokens, total_tokens

**Errors:**
- NO_MODEL_RUNNING: No inference server detected
- RUNTIME_NOT_RUNNING: Specified runtime not active
- INFERENCE_FAILED: Model failed to respond
- PARSE_ERROR: Invalid JSON from model API

**Example use:** "Ask the loaded model to review this code diff." / "Have qwen3 summarize this document."

---

## 5. Model Tasks

Bidirectional AI bridge tools. Local ↔ cloud as equal peers: local models handle privacy-sensitive and latency-critical tasks, cloud models handle complex reasoning and large-context work. The MCP server bridges both directions.

### optimac_model_task

Send a free-form task to the local model with file context. The model reads specified files, processes them with a custom prompt, and returns results.

**Parameters:**
- `prompt` (string): The task description
- `files` (string[], optional): Paths to include as context
- `system` (string, optional): Override system prompt

**Returns:** Model response with file context

**Example use:** "Ask the local model to explain this code"

---

### optimac_model_code_review

Run a local AI code review on the latest git diff in a repository. Uses safe `cwd`-based git commands with input validation.

**Parameters:**
- `repo_path` (string): Absolute path to git repository
- `branch` (string, optional): Branch to review (default: current)
- `against` (string, optional): Base branch to diff against (default: HEAD~1)

**Returns:** Code review with findings categorized by severity

**Example use:** "Review my latest commit in /path/to/repo"

---

### optimac_model_generate

Generate code from a natural-language description using the local model.

**Parameters:**
- `description` (string): What to generate
- `language` (string, optional): Target language (default: inferred)
- `output_file` (string, optional): Where to write the result

**Returns:** Generated code

---

### optimac_model_edit

Edit existing files using natural-language instructions. Reads the file, sends it to the local model with the instructions, and writes back the result.

**Parameters:**
- `file_path` (string): File to edit
- `instructions` (string): What to change
- `create_backup` (boolean, optional): Create .bak file first (default true)

**Returns:** Diff of changes, write confirmation

**Safety:** Validates file paths with `isPathSafe` to prevent writes outside home directory.

---

### optimac_model_summarize

Summarize one or more files using the local model.

**Parameters:**
- `files` (string[]): Files to summarize
- `style` (string, optional): Summary style ("brief", "detailed", "technical")

**Returns:** Summary text

---

### optimac_model_commit

Generate a conventional commit message from the current git diff using the local model. Uses safe `cwd`-based git commands with sanitized refs.

**Parameters:**
- `repo_path` (string): Absolute path to git repository
- `auto_commit` (boolean, optional): Stage and commit automatically (default false)

**Returns:** Generated commit message, optional commit confirmation

---

### optimac_cloud_escalate

Escalate a task to a cloud AI provider (OpenAI, Anthropic, Google) when local models can't handle the complexity. Requires API keys set in environment variables.

**Parameters:**
- `prompt` (string): The task to send to the cloud
- `provider` (string, optional): "openai", "anthropic", or "google" (default: openai)
- `model` (string, optional): Specific model (default: provider's latest)
- `files` (string[], optional): Files to include as context

**Returns:** Cloud model response with provider info and usage stats

---

### optimac_model_route

Smart router: sends a task to the local model first, evaluates response quality, and automatically escalates to cloud if the response is insufficient. Implements the bidirectional 50/50 philosophy.

**Parameters:**
- `prompt` (string): The task to route
- `files` (string[], optional): Files to include as context
- `cloud_provider` (string, optional): Fallback cloud provider (default: openai)
- `output_file` (string, optional): Write result to file

**Returns:** Response with routing metadata: where it was executed, whether it was escalated, quality assessment

**Example use:** "Route this task to the best available model"

---

## 6. Memory Pressure

Tiered memory management tools.

### optimac_memory_pressure_check

Evaluate current memory pressure and take action if thresholds are exceeded.

Behavior by level:
- NOMINAL (<75% used): Report only
- WARNING (75-90%): Report + list high-memory non-protected processes
- CRITICAL (>90%): Report + purge + auto-kill non-protected processes (if enabled)

**Parameters:**
- `dry_run` (boolean, optional): Report without taking action (default false)

**Returns:** Pressure level, actions taken, process list

**Example use:** "Check memory pressure and clean up if needed"

---

### optimac_maintenance_cycle

Run a complete maintenance cycle (8 steps): memory pressure check, purge memory, flush DNS, flush routes, clear caches, check disk space, verify AI stack health, report summary.

**Parameters:** none

**Returns:** Step-by-step results of each maintenance action

**Example use:** "Run full system maintenance"

---

## 8. Autonomy

Background monitoring, audit logging, and system health tracking.

### optimac_watchdog_start

Start the background watchdog that monitors memory pressure and AI stack health on a configurable interval. Auto-purges memory at critical pressure.

**Parameters:**
- `interval_minutes` (number, optional): Check interval in minutes (default: from config maintenanceIntervalSec, typically 360 = 6h)

**Returns:** Watchdog status (running, intervalMs, checksPerformed, lastCheck, autoActions)

**Example use:** "Start monitoring my system every 30 minutes"

---

### optimac_watchdog_stop

Stop the background watchdog.

**Parameters:** none

**Returns:** Watchdog status

---

### optimac_watchdog_status

Get current watchdog status: running state, interval, checks performed, and auto-actions taken.

**Parameters:** none

**Returns:** Watchdog status object

---

### optimac_audit_read

Read the most recent entries from the OptiMac audit log (~/.optimac/audit.jsonl). Returns structured tool execution history with timing, result status, and error details.

**Parameters:**
- `limit` (number, optional): Number of entries to return (default 50, max 500)
- `tool_filter` (string, optional): Filter entries by tool name (e.g., "watchdog", "optimac_purge_memory")

**Returns:** Array of audit entries with timestamp, tool, args, result, durationMs, errorType

**Example use:** "Show me the last 10 watchdog actions"

---

## 7. Configuration

Manage OptiMac settings at ~/.optimac/config.json. Shared between MCP server and GUI.

### optimac_config_get

Read the current configuration.

**Parameters:** none

**Returns:** Full config.json contents

---

### optimac_config_set

Modify a specific configuration value.

**Parameters:**
- `key` (string): One of: memoryWarningThreshold, memoryCriticalThreshold, autoKillAtCritical, maxProcessRSSMB, maintenanceIntervalSec
- `value` (any): New value (type must match expected)

**Returns:** Confirmation with old and new values

---

### optimac_config_protect_process

Add a process name to the protected list. Protected processes cannot be auto-killed during memory pressure events.

**Parameters:**
- `process_name` (string): Name or substring to match

**Returns:** Updated protected list

---

### optimac_config_unprotect_process

Remove a process name from the protected list.

**Parameters:**
- `process_name` (string): Exact name to remove

**Returns:** Updated protected list

---

### optimac_config_set_port

Configure the port for an AI inference service.

**Parameters:**
- `service` (string): "ollama", "lmstudio", or "mlx"
- `port` (number): Port number (1024-65535)

**Returns:** Confirmation

---

### optimac_debloat

Apply a debloat preset to disable unnecessary macOS services.

**Parameters:**
- `preset` (string): "minimal", "moderate", or "aggressive"

Presets (each includes all services from previous levels):
- minimal: Siri, Notification Center, iCloud sync (3 services)
- moderate: + Photo analysis, media analysis, suggestions, Handoff (8 services)
- aggressive: + Location services, App Store auto-updates, Time Machine (12 services)

**Returns:** List of services disabled

---

## RAM Headroom Policy

The model management tools enforce a 20% headroom policy to prevent swap thrashing on Apple Silicon. This means:

- A 4GB model requires 4.8GB of available RAM
- A 7GB model requires 8.4GB of available RAM
- A 14GB model requires 16.8GB of available RAM

The headroom covers inference overhead (KV cache, attention buffers, tokenizer), system processes, and prevents the system from entering memory pressure states that degrade performance.

To override this safety check, set `force=true` on `optimac_model_serve`. This is not recommended as it may cause significant swap usage and degrade inference speed.

## Typical Workflows

**Check what you can run:**
1. `optimac_models_available` - see all local models that fit in RAM
2. `optimac_model_ram_check size_gb=7` - check a specific size

**Load a model:**
1. `optimac_ollama_available` - see Ollama models that fit
2. `optimac_model_serve runtime=ollama model=llama3.2:3b` - serve it

**Switch models:**
1. `optimac_model_unload runtime=all` - free current model
2. `optimac_purge_memory` - reclaim pages
3. `optimac_model_serve runtime=ollama model=qwen2.5:7b` - load new one

Or use the one-step `optimac_swap_model runtime=ollama model=qwen2.5:7b`.

**Optimize for inference:**
1. `optimac_power_optimize` - set power for always-on
2. `optimac_reduce_ui_overhead` - free GPU resources
3. `optimac_disable_spotlight` - reduce I/O competition
4. `optimac_debloat preset=moderate` - kill background services
