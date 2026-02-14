# OptiMac MCP Server Test Results

**Test Date:** 2026-02-13 22:18:16
**Total Tools:** 61
**Status:** ✅ 29 PASS | ❌ 16 FAIL | ⏭️ 16 SKIP | ⚠️ 0 ERROR

## Summary by Category

### SYSTEM MONITORING (5/6 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_memory_status` | ✅ PASS | 5ms |  |
| `optimac_top_processes` | ✅ PASS | 36ms |  |
| `optimac_disk_usage` | ✅ PASS | 3ms |  |
| `optimac_thermal_status` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_power_settings` | ✅ PASS | 9ms |  |
| `optimac_system_overview` | ✅ PASS | 171ms |  |

### SYSTEM CONTROL (0/14 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_purge_memory` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_flush_dns` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_flush_routes` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_set_power` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_power_optimize` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |
| `optimac_kill_process` | ❌ FAIL | 2ms | Error: No process found with PID 99999 |
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
| `optimac_ai_stack_status` | ✅ PASS | 27ms |  |
| `optimac_ollama_start` | ✅ PASS | 5005ms |  |
| `optimac_ollama_stop` | ✅ PASS | 2022ms |  |
| `optimac_ollama_models` | ✅ PASS | 1695ms |  |
| `optimac_mlx_serve` | ❌ FAIL | 8ms | {
  "status": "not_installed",
  "install": "pip i |
| `optimac_mlx_stop` | ✅ PASS | 2022ms |  |
| `optimac_swap_model` | ✅ PASS | 8495ms |  |

### MODEL MANAGEMENT (7/9 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_models_available` | ✅ PASS | 17ms |  |
| `optimac_ollama_available` | ✅ PASS | 33ms |  |
| `optimac_model_serve` | ✅ PASS | 541ms |  |
| `optimac_model_unload` | ✅ PASS | 16ms |  |
| `optimac_models_running` | ✅ PASS | 14ms |  |
| `optimac_model_dir_set` | ❌ FAIL | 1ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_dir_get` | ✅ PASS | 1ms |  |
| `optimac_model_ram_check` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_chat` | ✅ PASS | 3420ms |  |

### MODEL TASKS (1/9 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_model_task` | ✅ PASS | 307ms |  |
| `optimac_model_code_review` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_generate` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_edit` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_summarize` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_commit` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_cloud_escalate` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_edge_escalate` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_model_route` | ❌ FAIL | 176ms | {
  "error": "ESCALATION_FAILED",
  "reason": "No  |

### EDGE TOOLS (3/4 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_edge_add` | ✅ PASS | 11ms |  |
| `optimac_edge_remove` | ✅ PASS | 0ms |  |
| `optimac_edge_list` | ✅ PASS | 0ms |  |
| `optimac_edge_test` | ❌ FAIL | 0ms | {
  "error": "NOT_FOUND",
  "name": "test-edge",
  |

### MEMORY PRESSURE (1/2 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_memory_pressure_check` | ✅ PASS | 46ms |  |
| `optimac_maintenance_cycle` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |

### CONFIGURATION (2/6 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_config_get` | ✅ PASS | 0ms |  |
| `optimac_config_set` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_config_protect_process` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_config_unprotect_process` | ❌ FAIL | 0ms | MCP error -32602: Input validation error: Invalid  |
| `optimac_config_set_port` | ✅ PASS | 0ms |  |
| `optimac_debloat` | ⏭️ SKIP | - | Requires sudo (passwordless not configured) |

### AUTONOMY (4/4 passed)

| Tool | Status | Duration | Notes |
|------|--------|----------|-------|
| `optimac_watchdog_start` | ✅ PASS | 7ms |  |
| `optimac_watchdog_stop` | ✅ PASS | 0ms |  |
| `optimac_watchdog_status` | ✅ PASS | 0ms |  |
| `optimac_audit_read` | ✅ PASS | 0ms |  |

## Failed Tests Detail

### optimac_kill_process
- **Status:** FAIL
- **Reason:** Error: No process found with PID 99999

### optimac_mlx_serve
- **Status:** FAIL
- **Reason:** {
  "status": "not_installed",
  "install": "pip install mlx-lm --break-system-packages"
}

### optimac_model_dir_set
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_dir_set: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "path"
    ],
    "message": "Required"
  }
]

### optimac_model_ram_check
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_ram_check: [
  {
    "code": "invalid_type",
    "expected": "number",
    "received": "undefined",
    "path": [
      "size_gb"
    ],
    "message": "Required"
  }
]

### optimac_model_code_review
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_code_review: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "repo_path"
    ],
    "message": "Required"
  }
]

### optimac_model_generate
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_generate: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "output_path"
    ],
    "message": "Required"
  }
]

### optimac_model_edit
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_edit: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "file_path"
    ],
    "message": "Required"
  },
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "instructions"
    ],
    "message": "Required"
  }
]

### optimac_model_summarize
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_summarize: [
  {
    "code": "invalid_type",
    "expected": "array",
    "received": "undefined",
    "path": [
      "paths"
    ],
    "message": "Required"
  }
]

### optimac_model_commit
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_model_commit: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "repo_path"
    ],
    "message": "Required"
  }
]

### optimac_cloud_escalate
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_cloud_escalate: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "prompt"
    ],
    "message": "Required"
  }
]

### optimac_edge_escalate
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_edge_escalate: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "prompt"
    ],
    "message": "Required"
  },
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "edge_endpoint"
    ],
    "message": "Required"
  }
]

### optimac_model_route
- **Status:** FAIL
- **Reason:** {
  "error": "ESCALATION_FAILED",
  "reason": "No API key for openrouter. Configure in ~/.optimac/config.json",
  "localAttempted": true
}

### optimac_edge_test
- **Status:** FAIL
- **Reason:** {
  "error": "NOT_FOUND",
  "name": "test-edge",
  "available": []
}

### optimac_config_set
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_config_set: [
  {
    "received": "testKey",
    "code": "invalid_enum_value",
    "options": [
      "memoryWarningThreshold",
      "memoryCriticalThreshold",
      "autoKillAtCritical",
      "maxProcessRSSMB",
      "maintenanceIntervalSec"
    ],
    "path": [
      "key"
    ],
    "message": "Invalid enum value. Expected 'memoryWarningThreshold' | 'memoryCriticalThreshold' | 'autoKillAtCritical' | 'maxProcessRSSMB' | 'maintenanceIntervalSec', received 'testKey'"
  },
  {
    "code": "invalid_union",
    "unionErrors": [
      {
        "issues": [
          {
            "code": "invalid_type",
            "expected": "number",
            "received": "string",
            "path": [
              "value"
            ],
            "message": "Expected number, received string"
          }
        ],
        "name": "ZodError"
      },
      {
        "issues": [
          {
            "code": "invalid_type",
            "expected": "boolean",
            "received": "string",
            "path": [
              "value"
            ],
            "message": "Expected boolean, received string"
          }
        ],
        "name": "ZodError"
      }
    ],
    "path": [
      "value"
    ],
    "message": "Invalid input"
  }
]

### optimac_config_protect_process
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_config_protect_process: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "process_name"
    ],
    "message": "Required"
  }
]

### optimac_config_unprotect_process
- **Status:** FAIL
- **Reason:** MCP error -32602: Input validation error: Invalid arguments for tool optimac_config_unprotect_process: [
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "process_name"
    ],
    "message": "Required"
  }
]

