# Remaining MCP Tools — Manual Test Results

**Date:** 2026-02-15 02:01:24
**Result:** 11 passed, 6 failed, 0 skipped

| # | Tool | Category | Status | Time | Output |
|---|------|----------|--------|------|--------|
| 1 | `optimac_thermal_status` | SysMon | ✅ PASS | 0.03s | {   "note": "powermetrics requires sudo. Showing pmset therm... |
| 2 | `optimac_sec_audit_auth` | Security | ❌ FAIL | 1.62s | Log query failed:... |
| 3 | `optimac_nvram_perf_mode` | SysCtrl | ✅ PASS | 0.0s | {   "serverPerfMode": "disabled",   "bootArgs": "(none)",   ... |
| 4 | `optimac_sys_eject` | SysCtrl | ✅ PASS | 10.96s | All ejectable drives ejected... |
| 5 | `optimac_sys_trash` | SysCtrl | ✅ PASS | 3.2s | Trash emptied successfully... |
| 6 | `optimac_config_set` | Config | ❌ FAIL | 0.0s | MCP error -32602: Input validation error: Invalid arguments ... |
| 7 | `optimac_config_get` | Config | ✅ PASS | 0.0s | {   "protectedProcesses": [     "ollama",     "lmstudio",   ... |
| 8 | `optimac_config_set` | Config | ❌ FAIL | 0.0s | MCP error -32602: Input validation error: Invalid arguments ... |
| 9 | `optimac_ollama_available` | ModelMgmt | ✅ PASS | 0.03s | {   "availableRAM_GB": 24.4,   "headroomPolicy": "20% above ... |
| 10 | `optimac_model_dir_get` | ModelMgmt | ✅ PASS | 0.0s | {   "modelBaseDir": "/Volumes/M2 Raid0/AI Models",   "exists... |
| 11 | `optimac_model_ram_check` | ModelMgmt | ❌ FAIL | 0.0s | MCP error -32602: Input validation error: Invalid arguments ... |
| 12 | `optimac_model_chat` | ModelMgmt | ❌ FAIL | 0.0s | MCP error -32602: Input validation error: Invalid arguments ... |
| 13 | `optimac_model_task` | ModelTask | ✅ PASS | 0.92s | {   "model": "llama3:latest",   "runtime": "ollama",   "file... |
| 14 | `optimac_model_summarize` | ModelTask | ❌ FAIL | 0.0s | MCP error -32602: Input validation error: Invalid arguments ... |
| 15 | `optimac_model_route` | ModelTask | ✅ PASS | 0.28s | {   "executedOn": "local (failed)",   "model": "llama3:lates... |
| 16 | `optimac_edge_list` | Edge | ✅ PASS | 0.0s | {   "count": 0,   "endpoints": [],   "message": "No edge end... |
| 17 | `optimac_watchdog_status` | Autonomy | ✅ PASS | 0.0s | {   "running": false,   "intervalMs": 21600000,   "checksPer... |

**Memory:** 24354MB → 25805MB (Δ+1451MB)