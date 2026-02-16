# OptiMac MCP Live Test Results

**Date:** 2026-02-15 01:21:46
**Duration:** 3.7s
**Tools Tested:** 22 (safe, non-network, non-destructive)
**Server Tools Available:** 89

## Summary
| Status | Count |
|--------|-------|
| ✅ PASS | 22 |
| ❌ FAIL | 0 |
| ⏰ TIMEOUT/ERROR | 0 |
| ⏭ SKIP | 0 |

## System State

### Baseline (Before Tests)
```
**Start**
  Memory: 24.19GB used / 48.0GB total (50.4% pressure) | Free: 1.51GB | Inactive: 20.84GB | Purgeable: 1.62GB | Compressed: 0.0GB
  Swap: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)
  Load: { 2.22 1.88 1.70 }
```

### Final (After All Tests)
```
**End**
  Memory: 24.15GB used / 48.0GB total (50.3% pressure) | Free: 1.53GB | Inactive: 20.85GB | Purgeable: 1.56GB | Compressed: 0.0GB
  Swap: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)
  Load: { 2.22 1.88 1.70 }
```

### Overall Delta
```
  Δ Used: -0.04GB | Δ Free: +0.02GB | Δ Pressure: -0.1%
```

## System Monitoring

### ✅ `optimac_system_overview` — PASS (0.21s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "hostname": "Mac-mini.local",
  "uptime": "1:21  up 1 day,  3:50, 2 users, load averages: 2.22 1.88 1.70",
  "memory": {
    "totalMB": 49152,
    "usedMB": 24768,
    "freeMB": 24384,
    "compressedMB": 2,
    "swapUsedMB": 0,
    "pressureLevel": "nominal"
  },
  "topProcessesByMemory": [
    {
      "pid": null,
      "command": "/Applications/Brave Browser.app/Contents/Frameworks/Brave Br",
      "rssMB": 2236,
      "cpuPercent": 0
    },
    {
      "pid": null,
      "command": "/System/Library/Frameworks/Virtualization.framework/Versions",
      "rssMB": 2196,
      "cpuPercent": 0.4
    },
    {
      "pid": null,
      "command": "/Applications/Antigravity.app/Contents/Resources/app/extensi",
      "rssMB": 1538,
      "cpuPercent": 13.3
    },
    {
      "pid": null,
      "command": "/Applications/Antigravity.app/Contents/Frameworks/Antigravit",
      "rssMB": 960,
      "cpuPercent": 22.4
    },
    {
      "pid": null,
      "command": "/Applications/Microsoft Teams.app/Contents/Helpers/Microsoft",
      "rssMB": 919,
      "cpuPercent": 0
    }
  ],
  "disk": [
    {
      "mount": "/",
      "usedPercent": 8,
      "availableMB": 134917
    },
    {
      "mount": "/System/Volumes/Data",
      "usedPercent": 71,
      "availableMB": 134917
    }
  ],
  "power": {
    "sleep": 0,
    "autorestart": 1,
    "womp": 1,
    "powernap": 0
  },
  "aiStack": {
    "ollama": "running",
    "lmstudio": "stopped",
    "mlx": "stopped"
  }
}
```
</details>

### ✅ `optimac_memory_status` — PASS (0.0s)
**System Impact:**
```
  Δ Used: -0.02GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "pageSize": 16384,
  "freePages": 100099,
  "activePages": 1384330,
  "inactivePages": 1365800,
  "speculativePages": 60377,
  "wiredPages": 199493,
  "compressedPages": 127,
  "purgeablePages": 104691,
  "fileBacked": 12213,
  "anonymous": 31701,
  "swapUsedMB": 0,
  "totalPhysicalMB": 49152,
  "usedMB": 24749,
  "freeMB": 24403,
  "pressureLevel": "nominal",
  "thresholds": {
    "warningAt": "75%",
    "criticalAt": "90%",
    "autoKillEnabled": true
  }
}
```
</details>

### ✅ `optimac_top_processes` — PASS (0.05s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
[
  {
    "pid": null,
    "user": "1912",
    "cpuPercent": 0,
    "memPercent": 4.6,
    "rssMB": 2236,
    "vsizeMB": 1846585,
    "state": "S",
    "command": "/Applications/Brave Browser.app/Contents/Frameworks/Brave Browser Framework.framework/Versions/144.1.86.148/Helpers/Brave Browser Helper (Renderer).app/Contents/MacOS/Brave Browser Helper (Renderer) --type=renderer --enable-distillability-service --origin-trial-public-key=bYUKPJoPnCxeNvu72j4EmPuK7tr1PAC7SHh8ld9Mw3E=,fMS4mpO6buLQ/QMd+zJmxzty/VQ6B1EUZqoCU04zoRU= --lang=en-US --num-raster-threads=4 --enable-zero-copy --enable-gpu-memory-buffer-compositor-resources --enable-main-frame-before-activation --renderer-client-id=36 --time-ticks-at-unix-epoch=-1771039869768006 --launch-time-ticks=402964051 --shared-files --metrics-shmem-handle=1752395122,r,11648997100834432478,12180639588793021667,2097152 --field-trial-handle=1718379636,r,1555081863903348421,344122889857730464,262144 --variations-seed-version=main@e9a5f7646c98664dc0d32ac63a0258e6a2dce7a2 --trace-process-track-uuid=3190709020045378058 --seatbelt-client=176",
    "protected": false
  },
  {
    "pid": null,
    "user": "76886",
    "cpuPercent": 0.4,
    "memPercent": 4.5,
    "rssMB": 2196,
    "vsizeMB": 429420,
    "state": "Ss",
    "command": "/System/Library/Frameworks/Virtualization.framework/Versions/A/XPCServices/com.apple.Virtualization.VirtualMachine.xpc/Contents/MacOS/com.apple.Virtualization.VirtualMachine",
    "protected": false
  },
  {
    "pid
... (truncated)
```
</details>

### ✅ `optimac_disk_usage` — PASS (0.0s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
[
  {
    "filesystem": "/dev/disk3s1s1",
    "sizeMB": 471482,
    "usedMB": 11698,
    "availableMB": 134917,
    "usedPercent": 8,
    "mountPoint": "/"
  },
  {
    "filesystem": "/dev/disk3s6",
    "sizeMB": 471482,
    "usedMB": 0,
    "availableMB": 134917,
    "usedPercent": 1,
    "mountPoint": "/System/Volumes/VM"
  },
  {
    "filesystem": "/dev/disk3s2",
    "sizeMB": 471482,
    "usedMB": 7749,
    "availableMB": 134917,
    "usedPercent": 6,
    "mountPoint": "/System/Volumes/Preboot"
  },
  {
    "filesystem": "/dev/disk3s4",
    "sizeMB": 471482,
    "usedMB": 12,
    "availableMB": 134917,
    "usedPercent": 1,
    "mountPoint": "/System/Volumes/Update"
  },
  {
    "filesystem": "/dev/disk1s2",
    "sizeMB": 500,
    "usedMB": 6,
    "availableMB": 483,
    "usedPercent": 2,
    "mountPoint": "/System/Volumes/xarts"
  },
  {
    "filesystem": "/dev/disk1s1",
    "sizeMB": 500,
    "usedMB": 6,
    "availableMB": 483,
    "usedPercent": 2,
    "mountPoint": "/System/Volumes/iSCPreboot"
  },
  {
    "filesystem": "/dev/disk1s3",
    "sizeMB": 500,
    "usedMB": 1,
    "availableMB": 483,
    "usedPercent": 1,
    "mountPoint": "/System/Volumes/Hardware"
  },
  {
    "filesystem": "/dev/disk3s5",
    "sizeMB": 471482,
    "usedMB": 315786,
    "availableMB": 134917,
    "usedPercent": 71,
    "mountPoint": "/System/Volumes/Data"
  },
  {
    "filesystem": "/dev/disk8",
    "sizeMB": 7630240,
    "usedMB": 806411,
    "availableMB": 6823828,
    "usedPercent": 1
... (truncated)
```
</details>

### ✅ `optimac_power_settings` — PASS (0.01s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: -0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "standby": 0,
  "Sleep": "On",
  "autorestart": 1,
  "SleepServices": 0,
  "powernap": 0,
  "networkoversleep": 1,
  "disksleep": 0,
  "sleep": 0,
  "ttyskeepawake": 1,
  "displaysleep": 0,
  "tcpkeepalive": 1,
  "powermode": 2,
  "womp": 1
}
```
</details>

### ✅ `optimac_battery_health` — PASS (0.07s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "battery": [
    "AC Charger Information:"
  ]
}
```
</details>

### ✅ `optimac_io_stats` — PASS (1.01s)
**System Impact:**
```
  Δ Used: +0.01GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
disk0              disk11              disk13               disk4 
    KB/t  tps  MB/s     KB/t  tps  MB/s     KB/t  tps  MB/s     KB/t  tps  MB/s 
   17.27   72  1.21     4.03    0  0.00     4.02    0  0.00     4.02    0  0.00 
    4.00    1  0.00     0.00    0  0.00     0.00    0  0.00     0.00    0  0.00
```
</details>

## Security

### ✅ `optimac_sec_status` — PASS (0.05s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "SIP": "System Integrity Protection status: enabled.",
  "Gatekeeper": "assessments enabled",
  "FileVault": "FileVault is On.",
  "Firewall": "Firewall is disabled. (State = 0)"
}
```
</details>

### ✅ `optimac_sec_firewall` — PASS (0.0s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "globalState": "Firewall is disabled. (State = 0)",
  "stealthMode": "Firewall stealth mode is off",
  "blockAll": "Firewall has block all state set to disabled."
}
```
</details>

### ✅ `optimac_sec_audit_ports` — PASS (0.05s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: -0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "totalListening": 17,
  "suspiciousCount": 6,
  "suspiciousEntries": [
    "synergy-s   859 gerdsenai   21u  IPv4 0x73d03ef1a1bdb8e7      0t0  TCP 127.0.0.1:24803 (LISTEN)",
    "synergy-s   859 gerdsenai   23u  IPv4 0x2715c12486e94398      0t0  TCP *:24802 (LISTEN)",
    "LM\\x20Stu   891 gerdsenai   70u  IPv4 0x3ec4fd3bcc3f6cea      0t0  TCP 127.0.0.1:41343 (LISTEN)",
    "OneDrive    897 gerdsenai   34u  IPv6  0xb7e0e30032f6449      0t0  TCP [::1]:42050 (LISTEN)",
    "Google      946 gerdsenai   44u  IPv6 0xd9aa016f93aa0967      0t0  TCP [::1]:7679 (LISTEN)",
    "synergy-c   994 gerdsenai    3u  IPv4 0x101dda490ca73c5e      0t0  TCP *:24800 (LISTEN)"
  ],
  "allEntries": [
    "rapportd    647 gerdsenai    8u  IPv4 0x79e64fd5e61fe374      0t0  TCP *:49153 (LISTEN)",
    "rapportd    647 gerdsenai   11u  IPv6 0x26868fe05360102f      0t0  TCP *:49153 (LISTEN)",
    "synergy-s   859 gerdsenai   21u  IPv4 0x73d03ef1a1bdb8e7      0t0  TCP 127.0.0.1:24803 (LISTEN)",
    "synergy-s   859 gerdsenai   23u  IPv4 0x2715c12486e94398      0t0  TCP *:24802 (LISTEN)",
    "LM\\x20Stu   891 gerdsenai   70u  IPv4 0x3ec4fd3bcc3f6cea      0t0  TCP 127.0.0.1:41343 (LISTEN)",
    "OneDrive    897 gerdsenai   34u  IPv6  0xb7e0e30032f6449      0t0  TCP [::1]:42050 (LISTEN)",
    "LensServi   941 gerdsenai  342u  IPv4 0xc6d70b040e4848d1      0t0  TCP 127.0.0.1:49260 (LISTEN)",
    "Google      946 gerdsenai   44u  IPv6 0xd9aa016f93aa0967      0t0  TCP [::1]:7679 (LISTEN)",
    "synergy-c   
... (truncated)
```
</details>

### ✅ `optimac_sec_audit_malware` — PASS (0.0s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "status": "suspicious_items_found",
  "checkedLocations": 3,
  "findings": [
    "[Suspicious Plist] /Users/gerdsenai/Library/LaunchAgents/ai.perplexity.xpc.plist",
    "[Suspicious Plist] /Users/gerdsenai/Library/LaunchAgents/com.symless.synergy3.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.google.keystone.agent.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.google.keystone.xpcservice.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.microsoft.OneDriveStandaloneUpdater.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.microsoft.SyncReporter.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.microsoft.update.agent.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.poly.CallControlApp.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.poly.LegacyHostApp.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.poly.LensControlService.plist",
    "[Suspicious Plist] /Library/LaunchAgents/com.symless.synergy-agent.plist",
    "[Suspicious Plist] /Library/LaunchAgents/us.zoom.updater.login.check.plist",
    "[Suspicious Plist] /Library/LaunchAgents/us.zoom.updater.plist",
    "[Suspicious Plist] /Library/LaunchDaemons/com.docker.socket.plist",
    "[Suspicious Plist] /Library/LaunchDaemons/com.docker.vmnetd.plist",
    "[Suspicious Plist] /Library/LaunchDaemons/com.google.GoogleUpdater.wake.system.plist",
    "[Suspicious Plist] /Library/LaunchDaemons/com.google.keystone.daemon.plist",
    "[Suspicious Plist] /Libra
... (truncated)
```
</details>

### ✅ `optimac_sec_audit_unsigned` — PASS (0.11s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: -0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "checked": 10,
  "unsignedCount": 0,
  "unsigned": []
}
```
</details>

### ✅ `optimac_sec_audit_connections` — PASS (0.05s)
**System Impact:**
```
  Δ Used: -0.01GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "establishedConnections": 68,
  "foreignConnections": 0,
  "foreign": []
}
```
</details>

## AI Stack

### ✅ `optimac_ai_stack_status` — PASS (0.09s)
**System Impact:**
```
  Δ Used: +0.01GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "ollama": {
    "running": true,
    "port": 11434,
    "models": [
      {
        "name": "llama3:latest",
        "sizeMB": 4445
      },
      {
        "name": "qwen3:8b",
        "sizeMB": 4983
      },
      {
        "name": "mychen76/qwen3_cline_roocode:4b",
        "sizeMB": 2499
      },
      {
        "name": "qwen3:4b-instruct-2507-q4_K_M",
        "sizeMB": 2382
      },
      {
        "name": "nomic-embed-text:latest",
        "sizeMB": 262
      },
      {
        "name": "qwen3-coder:30b",
        "sizeMB": 17697
      }
    ],
    "rssMB": 130,
    "pid": 6545
  },
  "lmstudio": {
    "running": false,
    "port": 1234
  },
  "mlx_server": {
    "running": false,
    "port": 8080
  },
  "openclaw": {
    "running": false,
    "pids": []
  },
  "claude_code": {
    "running": true,
    "pids": [
      2220,
      2265,
      76910
    ]
  }
}
```
</details>

### ✅ `optimac_ollama_models` — PASS (0.01s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
NAME                               ID              SIZE      MODIFIED     
llama3:latest                      365c0bd3c000    4.7 GB    6 weeks ago     
qwen3:8b                           500a1f067a9f    5.2 GB    2 months ago    
mychen76/qwen3_cline_roocode:4b    7a20cec43a8c    2.6 GB    4 months ago    
qwen3:4b-instruct-2507-q4_K_M      0edcdef34593    2.5 GB    4 months ago    
nomic-embed-text:latest            0a109f422b47    274 MB    4 months ago    
qwen3-coder:30b                    06c1097efce0    18 GB     4 months ago
```
</details>

### ✅ `optimac_gpu_stats` — PASS (1.26s)
**System Impact:**
```
  Δ Used: -0.01GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
**** GPU usage ****
GPU HW active frequency: 338 MHz
GPU HW active residency:   2.45% (338 MHz: 2.5% 618 MHz:   0% 796 MHz:   0% 924 MHz:   0% 952 MHz:   0% 1056 MHz:   0% 1062 MHz:   0% 1182 MHz:   0% 1182 MHz:   0% 1312 MHz:   0% 1242 MHz:   0% 1380 MHz:   0% 1326 MHz:   0% 1470 MHz:   0% 1578 MHz:   0%)
GPU SW requested state: (P1 : 100% P2 :   0% P3 :   0% P4 :   0% P5 :   0% P6 :   0% P7 :   0% P8 :   0% P9 :   0% P10 :   0% P11 :   0% P12 :   0% P13 :   0% P14 :   0% P15 :   0%)
GPU SW state: (SW_P1 : 2.6% SW_P2 :   0% SW_P3 :   0% SW_P4 :   0% SW_P5 :   0% SW_P6 :   0% SW_P7 :   0% SW_P8 :   0% SW_P9 :   0% SW_P10 :   0% SW_P11 :   0% SW_P12 :   0% SW_P13 :   0% SW_P14 :   0% SW_P15 :   0%)
GPU idle residency:  97.55%
GPU Power: 5 mW
```
</details>

### ✅ `optimac_models_running` — PASS (0.01s)
**System Impact:**
```
  Δ Used: -0.01GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "ram": {
    "totalGB": 48,
    "usedGB": 24.1,
    "availableGB": 23.9
  },
  "services": {
    "ollama": {
      "serverRunning": true,
      "port": 11434,
      "loadedModels": "NAME    ID    SIZE    PROCESSOR    CONTEXT    UNTIL"
    },
    "mlx": {
      "serverRunning": false
    },
    "lmstudio": {
      "serverRunning": false
    }
  }
}
```
</details>

### ✅ `optimac_models_available` — PASS (0.02s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "systemRAM": {
    "totalGB": 48,
    "usedGB": 24.2,
    "availableGB": 23.8
  },
  "headroomPolicy": "20% above model size reserved for system + inference overhead",
  "searchedDirectories": [
    "/Volumes/M2 Raid0/AI Models",
    "/Users/gerdsenai/.ollama/models",
    "/Users/gerdsenai/.cache/huggingface/hub"
  ],
  "totalModelsFound": 112,
  "modelsShown": 112,
  "modelsFilteredOut": 0,
  "models": [
    {
      "path": "/Volumes/M2 Raid0/AI Models/DevQuasar/deepcogito.cogito-v2-preview-deepseek-671B-MoE-GGUF/deepcogito.cogito-v2-preview-deepseek-671B-MoE.Q4_K_M-00003-of-00031.gguf",
      "name": "deepcogito.cogito-v2-preview-deepseek-671B-MoE.Q4_K_M-00003-of-00031.gguf",
      "sizeMB": 13288,
      "sizeGB": 13,
      "extension": ".gguf",
      "directory": "/Volumes/M2 Raid0/AI Models",
      "fitsInRAM": true,
      "availableRAM_GB": 23.8,
      "requiredRAM_GB": 15.6
    },
    {
      "path": "/Volumes/M2 Raid0/AI Models/DevQuasar/deepcogito.cogito-v2-preview-deepseek-671B-MoE-GGUF/deepcogito.cogito-v2-preview-deepseek-671B-MoE.Q4_K_M-00004-of-00031.gguf",
      "name": "deepcogito.cogito-v2-preview-deepseek-671B-MoE.Q4_K_M-00004-of-00031.gguf",
      "sizeMB": 13288,
      "sizeGB": 13,
      "extension": ".gguf",
      "directory": "/Volumes/M2 Raid0/AI Models",
      "fitsInRAM": true,
      "availableRAM_GB": 23.8,
      "requiredRAM_GB": 15.6
    },
    {
      "path": "/Volumes/M2 Raid0/AI Models/DevQuasar/deepcogito.cogito-v2-preview-deepseek-671B-MoE
... (truncated)
```
</details>

## Config

### ✅ `optimac_config_get` — PASS (0.0s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "protectedProcesses": [
    "ollama",
    "lmstudio",
    "LM Studio",
    "mlx",
    "python3",
    "python",
    "node",
    "claude",
    "openclaw",
    "sshd",
    "WindowServer",
    "loginwindow",
    "launchd",
    "kernel_task",
    "mds_stores",
    "coreaudiod",
    "systemsoundserverd"
  ],
  "memoryWarningThreshold": 0.75,
  "memoryCriticalThreshold": 0.9,
  "autoKillAtCritical": true,
  "maxProcessRSSMB": 2048,
  "maintenanceIntervalSec": 21600,
  "dnsServers": [
    "1.1.1.1",
    "1.0.0.1"
  ],
  "spotlightExclusions": [
    "~/.ollama",
    "~/models",
    "~/.cache",
    "~/Library/Caches"
  ],
  "disabledServices": [],
  "aiStackPorts": {
    "ollama": 11434,
    "lmstudio": 1234,
    "mlx": 8080
  },
  "modelBaseDir": "/Volumes/M2 Raid0/AI Models",
  "cloudEndpoints": {
    "openrouter": {
      "url": "https://openrouter.ai/api/v1",
      "apiKey": "",
      "defaultModel": "anthropic/claude-sonnet-4"
    },
    "anthropic": {
      "url": "https://api.anthropic.com/v1",
      "apiKey": "",
      "defaultModel": "claude-sonnet-4-5-20250929"
    },
    "openai": {
      "url": "https://api.openai.com/v1",
      "apiKey": "",
      "defaultModel": "gpt-4o"
    }
  },
  "edgeEndpoints": {}
}
```
</details>

## System Misc

### ✅ `optimac_sys_login_items` — PASS (0.26s)
**System Impact:**
```
  Δ Used: -0.02GB | Δ Free: +0.01GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "count": 6,
  "items": [
    "Poly Studio",
    "Apps for Google App",
    "Google Drive",
    "Synergy",
    "LM Studio",
    "OneDrive Sync Service"
  ]
}
```
</details>

### ✅ `optimac_watchdog_status` — PASS (0.0s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "running": false,
  "intervalMs": 21600000,
  "checksPerformed": 0,
  "lastCheck": null,
  "autoActions": 0
}
```
</details>

### ✅ `optimac_memory_pressure_check` — PASS (0.06s)
**System Impact:**
```
  Δ Used: 0.0GB | Δ Free: 0.0GB | Δ Pressure: 0.0%
```
<details><summary>Output</summary>

```json
{
  "memoryUsedMB": 24730,
  "memoryTotalMB": 49152,
  "usedPercent": 50,
  "pressureLevel": "nominal",
  "swapUsedMB": 0,
  "level": "nominal",
  "action": "none",
  "message": "Memory usage is within normal bounds."
}
```
</details>
