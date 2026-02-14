# OptiMac MCP Server Test Results

**Test Date:** 2026-02-13 22:33:51
**Total Tools:** 61
**Status:** ✅ 38 PASS | ❌ 6 FAIL | ⏭️ 17 SKIP | ⚠️ 0 ERROR

## Summary by Category

### SYSTEM MONITORING (5/6 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_memory_status` | ✅ PASS | 4ms |  |
| `optimac_top_processes` | ✅ PASS | 37ms |  |
| `optimac_disk_usage` | ✅ PASS | 3ms |  |
| `optimac_thermal_status` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_power_settings` | ✅ PASS | 9ms |  |
| `optimac_system_overview` | ✅ PASS | 179ms |  |

### SYSTEM CONTROL (0/14 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_purge_memory` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_flush_dns` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_flush_routes` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_set_power` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_power_optimize` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_kill_process` | ❌ FAIL | 2ms | Refused: "/opt/homebrew/Cellar/python@3.14/3.14.3_ |
| `optimac_disable_service` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_enable_service` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_disable_spotlight` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_clear_caches` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_set_dns` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_network_reset` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_reduce_ui_overhead` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_nvram_perf_mode` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |

### AI STACK (6/7 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_ai_stack_status` | ✅ PASS | 71ms |  |
| `optimac_ollama_start` | ✅ PASS | 1ms |  |
| `optimac_ollama_stop` | ✅ PASS | 2013ms |  |
| `optimac_ollama_models` | ✅ PASS | 15ms |  |
| `optimac_mlx_serve` | ⏭️ SKIP | - | Requires MLX (mlx-lm not installed) |
| `optimac_mlx_stop` | ✅ PASS | 2016ms |  |
| `optimac_swap_model` | ✅ PASS | 8279ms |  |

### MODEL MANAGEMENT (8/9 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_models_available` | ✅ PASS | 13ms |  |
| `optimac_ollama_available` | ✅ PASS | 32ms |  |
| `optimac_model_serve` | ✅ PASS | 412ms |  |
| `optimac_model_unload` | ✅ PASS | 17ms |  |
| `optimac_models_running` | ✅ PASS | 15ms |  |
| `optimac_model_dir_set` | ❌ FAIL | 0ms | {"error":"Directory does not exist: /tmp/models"} |
| `optimac_model_dir_get` | ✅ PASS | 1ms |  |
| `optimac_model_ram_check` | ✅ PASS | 3ms |  |
| `optimac_model_chat` | ✅ PASS | 3442ms |  |

### MODEL TASKS (5/9 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_model_task` | ✅ PASS | 285ms |  |
| `optimac_model_code_review` | ✅ PASS | 8477ms |  |
| `optimac_model_generate` | ✅ PASS | 607ms |  |
| `optimac_model_edit` | ✅ PASS | 749ms |  |
| `optimac_model_summarize` | ❌ FAIL | 1ms | {"error":"No readable files found in the specified |
| `optimac_model_commit` | ✅ PASS | 21491ms |  |
| `optimac_cloud_escalate` | ❌ FAIL | 1ms | {
  "error": "NO_API_KEY",
  "provider": "openrout |
| `optimac_edge_escalate` | ❌ FAIL | 0ms | {
  "error": "ENDPOINT_NOT_FOUND",
  "edge_endpoin |
| `optimac_model_route` | ❌ FAIL | 261ms | {
  "error": "ESCALATION_FAILED",
  "reason": "No  |

### EDGE TOOLS (4/4 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_edge_add` | ✅ PASS | 12ms |  |
| `optimac_edge_test` | ✅ PASS | 15ms |  |
| `optimac_edge_list` | ✅ PASS | 7ms |  |
| `optimac_edge_remove` | ✅ PASS | 1ms |  |

### MEMORY PRESSURE (1/2 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_memory_pressure_check` | ✅ PASS | 43ms |  |
| `optimac_maintenance_cycle` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |

### CONFIGURATION (5/6 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_config_get` | ✅ PASS | 0ms |  |
| `optimac_config_set` | ✅ PASS | 1ms |  |
| `optimac_config_protect_process` | ✅ PASS | 0ms |  |
| `optimac_config_unprotect_process` | ✅ PASS | 0ms |  |
| `optimac_config_set_port` | ✅ PASS | 0ms |  |
| `optimac_debloat` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |

### AUTONOMY (4/4 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_watchdog_start` | ✅ PASS | 8ms |  |
| `optimac_watchdog_stop` | ✅ PASS | 0ms |  |
| `optimac_watchdog_status` | ✅ PASS | 0ms |  |
| `optimac_audit_read` | ✅ PASS | 0ms |  |

## Failed Tests Detail

### optimac_kill_process
- **Status:** FAIL
- **Reason:** Refused: "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python" (PID 6468) is a protected process. Use force=true to override. Protected list: ollama, lmstudio, LM Studio, mlx, python3, python, node, claude, openclaw, sshd, WindowServer, loginwindow, launchd, kernel_task, mds_stores, coreaudiod, systemsoundserverd

### optimac_model_dir_set
- **Status:** FAIL
- **Reason:** {"error":"Directory does not exist: /tmp/models"}

### optimac_model_summarize
- **Status:** FAIL
- **Reason:** {"error":"No readable files found in the specified paths."}

### optimac_cloud_escalate
- **Status:** FAIL
- **Reason:** {
  "error": "NO_API_KEY",
  "provider": "openrouter",
  "message": "No API key configured for openrouter. Set it in ~/.optimac/config.json under cloudEndpoints.openrouter.apiKey",
  "configPath": "~/.optimac/config.json"
}

### optimac_edge_escalate
- **Status:** FAIL
- **Reason:** {
  "error": "ENDPOINT_NOT_FOUND",
  "edge_endpoint": "test-edge",
  "available": [],
  "message": "Edge endpoint \"test-edge\" not configured. Use optimac_edge_add first."
}

### optimac_model_route
- **Status:** FAIL
- **Reason:** {
  "error": "ESCALATION_FAILED",
  "reason": "No API key for openrouter. Configure in ~/.optimac/config.json",
  "localAttempted": true
}

