# Mac Mini M4 / M4 Pro: Complete AI Inference Optimization Guide

## The Goal

Turn a Mac Mini M4 or M4 Pro into a dedicated, always-on, bloat-free AI inference machine running MLX workloads, local LLMs (via LM Studio, Ollama), AI agents (OpenClaw, Claude Code), and cloud-routed models (OpenRouter) -- all controllable via MCP servers that act as a system-level "IQ 3000 admin" managing power, memory, network, and processes 24/7/365.

---

## Part 1: Hardware Reality Check

### M4 vs M4 Pro for AI Inference

| Spec | M4 (base) | M4 Pro |
|------|-----------|--------|
| Memory bandwidth | 120 GB/s | 273 GB/s |
| Max unified memory | 32 GB | 64 GB |
| GPU cores | 10 | 20 |
| Neural Engine | 16-core, 38 TOPS | 16-core, 38 TOPS |
| Typical 8B 4-bit tok/s | 18-25 | 30-45 |
| Typical 32B 4-bit tok/s | Swap-bound at 16GB | 11-14 |
| Idle power draw | ~7W | ~10W |
| AI workload draw | ~25-30W | ~40-50W |
| Electricity cost/year | ~$15-25 | ~$25-40 |

**The bottleneck is memory bandwidth, not compute.** LLM inference is memory-bound because generating each token requires reading billions of weights from RAM with relatively little math per byte. The M4 Pro's 273 GB/s bandwidth is 2.3x the base M4, which translates nearly linearly to higher tokens/sec on larger models.

### RAM Configuration Guidance

- **16 GB**: Fine for 7-8B models only. Swap kills performance on anything larger. Workable for a single-purpose OpenClaw or Claude Code relay.
- **24 GB**: The minimum for serious work. Comfortably runs 14B quantized models. Can squeeze a 32B model at aggressive quantization with some swap.
- **32 GB**: The sweet spot. Runs 32B models at 4-bit comfortably. Multiple concurrent agents plus a model server.
- **48-64 GB (M4 Pro only)**: Production tier. Run 70B models at 4-bit, or multiple 32B models simultaneously.

---

## Part 2: MLX Inference Optimization

MLX is Apple's open-source ML framework built specifically for Apple Silicon. It uses Metal for GPU acceleration and exploits unified memory so CPU and GPU share the same data pool with zero-copy overhead.

### Why MLX Beats llama.cpp on M4

MLX is now significantly faster than llama.cpp on M4 Pro hardware. Apple has done M4-specific GPU optimizations in MLX that llama.cpp cannot replicate. MLX achieves the highest sustained generation throughput among major local LLM runtimes on Apple Silicon.

### Quantization Strategy

Quantization is the single biggest lever for fitting larger models into limited RAM.

**Recommended approach**: Use 4-bit quantization for the bulk of model weights, but keep embedding and final projection layers at 6-bit or 8-bit precision. These layers are more sensitive to quantization noise, so mixed precision here gives you the best quality-per-byte tradeoff.

Practical sizes after 4-bit quantization:
- 7-8B model: ~4-5 GB RAM
- 13-14B model: ~7-8 GB RAM
- 32B model: ~18-20 GB RAM
- 70B model: ~38-40 GB RAM

### MLX-Specific Tuning

1. **Always use MLX-format models** from Hugging Face (look for `mlx-community` repos). These are pre-converted and optimized.
2. **Keep MLX updated.** Apple ships performance improvements frequently -- a 5-10% gain per update is common.
3. **Use `mlx-lm` CLI** for direct inference without GUI overhead:
   ```bash
   pip install mlx-lm
   mlx_lm.generate --model mlx-community/Qwen2.5-32B-Instruct-4bit --prompt "Hello"
   ```
4. **Serve via `mlx-lm.server`** for OpenAI-compatible API endpoint:
   ```bash
   mlx_lm.server --model mlx-community/Qwen2.5-32B-Instruct-4bit --port 8080
   ```
5. **Monitor with `powermetrics`**:
   ```bash
   sudo powermetrics --samplers gpu_power,cpu_power -i 1000
   ```

### Thermal Management

The Mac Mini M4 is passively/actively cooled and handles sustained loads well, but for continuous 24/7 inference:
- Ensure adequate airflow around the device (do not stack or enclose)
- Vertical orientation exposes more surface area
- Consider an external USB fan pad for heavy sustained batch inference
- Monitor thermal throttling: `sudo powermetrics --samplers thermal`

---

## Part 3: Software Stack Setup

### LM Studio (Local GUI + Server)

LM Studio provides a polished GUI for downloading, managing, and serving local models with native MLX support.

**Setup:**
1. Download from [lmstudio.ai](https://lmstudio.ai)
2. In settings, enable MLX backend for Apple Silicon acceleration
3. Download models in MLX format for best M4 performance
4. Start the local server: `lms server start --port 1234`
5. Set context length to 32K minimum (bump to 128K for large projects if RAM allows)

**Connecting to Claude Code:**
```bash
export ANTHROPIC_BASE_URL=http://localhost:1234
export ANTHROPIC_AUTH_TOKEN=lmstudio
claude --model openai/your-model-name
```

LM Studio 0.4.1+ has native Anthropic API compatibility, making Claude Code integration seamless.

### Ollama (Headless Server)

Best for headless/server deployments. Lighter weight than LM Studio.

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b-instruct-q4_0

# Run as server (default port 11434)
ollama serve

# Run interactively
ollama run llama3.1:8b-instruct-q4_0
```

**Critical**: Run Ollama natively, never in Docker. Native Metal GPU utilization hits ~100%. Docker on macOS runs in a VM layer, falling back to CPU only, resulting in 5-6x slower inference.

### OpenRouter (Cloud Routing)

For models too large to run locally, or for accessing Claude/GPT-4 class models:

```bash
export ANTHROPIC_BASE_URL=https://openrouter.ai/api
export ANTHROPIC_AUTH_TOKEN=your_openrouter_key
export ANTHROPIC_API_KEY=""  # Must be empty to prevent direct Anthropic auth
```

This lets Claude Code, or any OpenAI-compatible client, route through OpenRouter to access any model they host.

### OpenClaw (formerly Clawdbot / Moltbot)

OpenClaw is the most-hyped open-source AI agent of 2026 (147K+ GitHub stars). It connects LLMs to messaging apps (WhatsApp, Telegram, Discord, Slack, Signal, iMessage) with persistent memory, proactive notifications, and real action capabilities (file search, shell commands, Python scripts, calendar management, smart home control).

**Setup:**
1. Requires Node.js 22+, macOS 14+
2. One-liner install from [openclaw.ai](https://openclaw.ai)
3. Interactive TUI walks through configuration
4. QuickStart mode configures safe defaults

**Cost structure:**
- OpenClaw itself: free (MIT license)
- API tokens: ~$10-30/month light, $30-70 moderate, $70-150 heavy
- Can use Claude Pro/Max subscription via CLI token instead of per-token billing

**Security warning**: OpenClaw requires broad system permissions. Cisco's security team found third-party skills performing data exfiltration and prompt injection. Lock down permissions carefully, avoid untrusted skills, and monitor network traffic.

### Claude Code

Claude Code is Anthropic's official CLI for agentic coding. It can connect to local models as a fallback when API quota runs out.

**Local model setup:**
```bash
# Via LM Studio
export ANTHROPIC_BASE_URL=http://localhost:1234
export ANTHROPIC_AUTH_TOKEN=lmstudio
claude --model openai/qwen3-coder-30b

# Via Ollama + LiteLLM proxy
pip install litellm
litellm --model ollama/llama3.1 --port 4000
export ANTHROPIC_BASE_URL=http://localhost:4000
claude
```

**Hardware note**: Claude Code sends a ~16K token system prompt, so you need 32GB+ RAM for a genuinely usable experience with local models. At 16GB the experience is rough.

---

## Part 4: macOS Bloat Reduction for AI Workloads

The goal is to reclaim every MB of RAM and every cycle of bandwidth for model inference. A headless AI server does not need Spotlight, Siri, iCloud sync, Notification Center, AirDrop, or half the daemons macOS runs by default.

### Step 1: Disable Spotlight Indexing

Spotlight I/O competes directly with model memory mapping. This is the single highest-impact change.

```bash
# Disable Spotlight entirely
sudo mdutil -a -i off

# Or exclude specific directories (model storage, repos)
# System Settings > Siri & Spotlight > Spotlight Privacy > add folders
```

### Step 2: Disable Unnecessary Services via launchctl

```bash
# Disable Siri
launchctl disable user/$(id -u)/com.apple.Siri.agent

# Disable Notification Center
launchctl disable user/$(id -u)/com.apple.notificationcenterui.agent

# Disable iCloud sync daemon (bird)
launchctl disable user/$(id -u)/com.apple.bird

# Disable AirDrop
sudo launchctl disable system/com.apple.AirPlayXPCHelper

# Disable Universal Clipboard / Handoff
defaults write ~/Library/Preferences/ByHost/com.apple.coreservices.useractivityd.plist ActivityAdvertisingAllowed -bool no
defaults write ~/Library/Preferences/ByHost/com.apple.coreservices.useractivityd.plist ActivityReceivingAllowed -bool no

# Disable App Store auto-updates
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool false

# Disable Time Machine (if not backing up)
sudo tmutil disable

# Disable location services
sudo launchctl disable system/com.apple.locationd
```

### Step 3: Disable Visual Effects and Animations

```bash
# Reduce motion
defaults write com.apple.universalaccess reduceMotion -bool true

# Reduce transparency
defaults write com.apple.universalaccess reduceTransparency -bool true

# Disable window animations
defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false

# Speed up Mission Control animations
defaults write com.apple.dock expose-animation-duration -float 0.1

# Disable Dock auto-hide animation
defaults write com.apple.dock autohide-time-modifier -float 0

# Apply changes
killall Dock
killall Finder
```

### Step 4: Disable FileVault (for headless operation)

FileVault encryption creates a pre-boot authentication barrier that blocks remote access after restarts. For a headless AI server on a trusted network:

```bash
sudo fdesetup disable
```

### Step 5: Enable Auto-Login

System Settings > Users & Groups > Login Options > Automatic login > select your user

### Step 6: Kill Unnecessary Login Items

System Settings > General > Login Items > remove everything non-essential

### Step 7: Switch to Performance-Optimized DNS

```bash
# Cloudflare DNS (fastest)
sudo networksetup -setdnsservers Ethernet 1.1.1.1 1.0.0.1

# Or Google DNS
sudo networksetup -setdnsservers Ethernet 8.8.8.8 8.8.4.4
```

---

## Part 5: Power Management for Always-On Operation

### The pmset Configuration

```bash
# Apply all settings at once
sudo pmset -a \
  sleep 0 \
  displaysleep 0 \
  disksleep 0 \
  womp 1 \
  autorestart 1 \
  ttyskeepawake 1 \
  powernap 0

# Verify
pmset -g
```

| Setting | Value | What It Does |
|---------|-------|--------------|
| sleep 0 | Disable | Never sleep the system |
| displaysleep 0 | Disable | Never sleep the display |
| disksleep 0 | Disable | Never spin down disks |
| womp 1 | Enable | Wake on LAN (Magic Packet) |
| autorestart 1 | Enable | Auto-restart after power failure |
| ttyskeepawake 1 | Enable | Stay awake during SSH sessions |
| powernap 0 | Disable | No background wake cycles |

### Persistent Caffeinate Daemon

Create a LaunchDaemon that runs `caffeinate` at boot, keeping the Mac awake even at the login screen:

```bash
sudo tee /Library/LaunchDaemons/com.local.caffeinate.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.caffeinate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/com.local.caffeinate.plist
```

### HDMI Dummy Plug

Without a display connected, macOS may not initialize the graphics subsystem. A $5-10 HDMI dummy plug from Amazon tricks macOS into thinking a monitor is attached, ensuring Metal GPU acceleration works for MLX inference.

---

## Part 6: Automated Maintenance Scripts

### Memory Purge + Cache Flush Script

Save as `/usr/local/bin/ai-server-maintain.sh`:

```bash
#!/bin/bash
# AI Server Maintenance Script
# Run periodically via cron or launchd

LOG="/var/log/ai-server-maintain.log"
echo "$(date): Starting maintenance cycle" >> "$LOG"

# 1. Purge inactive memory
echo "$(date): Purging inactive memory..." >> "$LOG"
sudo purge 2>> "$LOG"

# 2. Flush DNS cache
echo "$(date): Flushing DNS cache..." >> "$LOG"
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder 2>> "$LOG"

# 3. Clear system caches (safe subset)
echo "$(date): Clearing temp files..." >> "$LOG"
sudo rm -rf /tmp/* 2>/dev/null
rm -rf ~/Library/Caches/com.apple.Safari/* 2>/dev/null

# 4. Clear old system logs (older than 7 days)
echo "$(date): Rotating logs..." >> "$LOG"
sudo find /var/log -name "*.log" -mtime +7 -delete 2>/dev/null
find ~/Library/Logs -name "*.log" -mtime +7 -delete 2>/dev/null

# 5. Flush network routing table stale entries
echo "$(date): Flushing network routes..." >> "$LOG"
sudo route -n flush 2>> "$LOG"

# 6. Reset mDNSResponder (fixes Bonjour/network discovery issues)
echo "$(date): Resetting mDNSResponder..." >> "$LOG"
sudo killall -HUP mDNSResponder 2>> "$LOG"

# 7. Report memory status
echo "$(date): Memory status:" >> "$LOG"
vm_stat >> "$LOG"

# 8. Report disk usage
echo "$(date): Disk usage:" >> "$LOG"
df -h / >> "$LOG"

echo "$(date): Maintenance complete" >> "$LOG"
echo "---" >> "$LOG"
```

```bash
chmod +x /usr/local/bin/ai-server-maintain.sh
```

### Schedule via LaunchDaemon (every 6 hours)

```bash
sudo tee /Library/LaunchDaemons/com.local.ai-maintenance.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.ai-maintenance</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ai-server-maintain.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>21600</integer>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/com.local.ai-maintenance.plist
```

### Stale Process Killer

Save as `/usr/local/bin/kill-stale-processes.sh`:

```bash
#!/bin/bash
# Kill processes consuming excessive memory or CPU that are not AI workloads

PROTECTED="ollama|lmstudio|mlx|python|node|claude"

# Find processes using >80% CPU for extended periods (excluding protected)
ps aux | awk -v prot="$PROTECTED" '
  NR>1 && $3>80.0 {
    cmd = $11
    if (cmd !~ prot) print $2, $3"%", cmd
  }
' | while read pid cpu cmd; do
    logger "ai-server: killing stale process $pid ($cmd) at $cpu CPU"
    kill -15 "$pid" 2>/dev/null
done

# Find processes using >2GB memory (excluding protected)
ps aux | awk -v prot="$PROTECTED" '
  NR>1 && $6>2097152 {
    cmd = $11
    if (cmd !~ prot) print $2, $6/1024"MB", cmd
  }
' | while read pid mem cmd; do
    logger "ai-server: flagging high-memory process $pid ($cmd) at ${mem}"
done
```

---

## Part 7: MCP Servers for System Control

This is the "IQ 3000 admin" layer. MCP (Model Context Protocol) servers let AI assistants control macOS programmatically. Here are the key projects:

### 1. macos-automator-mcp (by steipete)

**GitHub**: [github.com/steipete/macos-automator-mcp](https://github.com/steipete/macos-automator-mcp)

The most comprehensive option. Contains 200+ pre-programmed automation sequences. Runs AppleScript and JXA (JavaScript for Automation) to control any macOS application.

Capabilities include: toggle dark mode, manage windows, control system volume, manage Wi-Fi, read/write clipboard, launch/quit apps, manage notification settings, control Finder, manage Safari tabs, and much more.

**Requirements**: Accessibility permissions (System Settings > Privacy & Security > Accessibility) and Automation permissions (System Settings > Privacy & Security > Automation).

### 2. automation-mcp (by ashwwwin)

**GitHub**: [github.com/ashwwwin/automation-mcp](https://github.com/ashwwwin/automation-mcp)

Full desktop automation: mouse control, keyboard input, system shortcuts, screen reading. Useful for automating GUI interactions that AppleScript cannot reach.

### 3. apple-mcp (by supermemory.ai)

**GitHub**: [github.com/supermemoryai/apple-mcp](https://github.com/supermemoryai/apple-mcp)

Native Apple app integration: Notes, Contacts, Messages, Reminders. Natural language commands like "Read my conference notes, find contacts for the people I met, and send them a thank you message."

### 4. mcp-server-macos-use

Written in Swift, implements MCP for direct macOS UI control. Natural language to system actions -- click buttons, type text, read screen content. Lower barrier than writing AppleScript.

### 5. MacPilot MCP Server

Works with any MCP-compatible client (Claude Desktop, Cursor, etc.). Provides broad system management capabilities.

### Building a Custom "Admin Brain" MCP Server

For the "IQ 3000 admin on the fly 24/7/365" use case, you would want a custom MCP server that combines:

```
Tools to expose via MCP:
- purge_memory()       -> runs `sudo purge`
- flush_dns()          -> runs DNS flush commands
- flush_routes()       -> runs `sudo route -n flush`
- get_memory_stats()   -> parses `vm_stat` output
- get_cpu_load()       -> parses `top -l 1` output
- get_gpu_usage()      -> parses `sudo powermetrics` output
- get_thermal_status() -> reads thermal sensors
- get_disk_usage()     -> parses `df -h`
- kill_process(pid)    -> safely terminates a process
- get_top_processes()  -> lists top CPU/memory consumers
- set_power_mode(m)    -> adjusts pmset settings
- restart_service(s)   -> restarts a launchd service
- clear_caches()       -> clears safe cache directories
- network_diagnostics()-> runs ping, traceroute, etc.
- get_model_server_status() -> checks Ollama/LM Studio health
- restart_model_server()    -> restarts inference server
```

This is buildable with the `mcp-builder` skill I have available. The existing `macos-automator-mcp` covers about 70% of this surface area. The remaining 30% (AI-workload-specific monitoring and management) would need custom tooling.

### Connecting MCP to Claude Desktop or OpenClaw

In your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "macos-admin": {
      "command": "node",
      "args": ["/path/to/macos-automator-mcp/dist/index.js"],
      "env": {}
    }
  }
}
```

OpenClaw supports MCP servers as "skills" that extend its capabilities.

---

## Part 8: Remote Access Setup

### SSH (Essential)

```bash
# Enable SSH
sudo systemsetup -setremotelogin on

# Verify
sudo systemsetup -getremotelogin
```

### Tailscale (Zero-Config VPN)

For access from outside your local network without port forwarding:

1. Install Tailscale from [tailscale.com](https://tailscale.com)
2. Authenticate on the Mac Mini
3. Access from anywhere via Tailscale IP

### Screen Sharing

System Settings > General > Sharing > Screen Sharing > On

---

## Part 9: Complete Setup Checklist

### Initial Hardware Setup
- [ ] Choose RAM tier (32GB minimum recommended, 48-64GB ideal for M4 Pro)
- [ ] HDMI dummy plug installed
- [ ] Ethernet connected (not Wi-Fi, for lower latency and reliability)

### macOS Configuration
- [ ] pmset configured (sleep 0, autorestart 1, womp 1, etc.)
- [ ] Caffeinate daemon installed
- [ ] FileVault disabled
- [ ] Auto-login enabled
- [ ] Spotlight disabled (`sudo mdutil -a -i off`)
- [ ] Siri disabled
- [ ] iCloud sync disabled
- [ ] Notification Center disabled
- [ ] AirDrop disabled
- [ ] Visual effects reduced
- [ ] DNS switched to Cloudflare/Google
- [ ] SSH enabled
- [ ] Screen Sharing enabled
- [ ] Tailscale installed (optional, for remote access)

### AI Software Stack
- [ ] Ollama installed and configured as LaunchDaemon
- [ ] LM Studio installed (optional, for GUI model management)
- [ ] MLX and mlx-lm installed (`pip install mlx mlx-lm`)
- [ ] Models downloaded in MLX format (from mlx-community on HuggingFace)
- [ ] OpenClaw installed and configured (optional)
- [ ] Claude Code configured with local model fallback
- [ ] OpenRouter API key configured (optional, for cloud model access)

### MCP Layer
- [ ] macos-automator-mcp installed
- [ ] Accessibility permissions granted
- [ ] Automation permissions granted
- [ ] Custom admin MCP server built (optional)
- [ ] MCP servers connected to Claude Desktop / OpenClaw

### Maintenance
- [ ] ai-server-maintain.sh installed and scheduled
- [ ] kill-stale-processes.sh installed
- [ ] Monitoring configured (iStat Menus or custom)
- [ ] Log rotation configured

---

## Part 10: Performance Benchmarks to Expect

### M4 (base, 32GB RAM)

| Model | Quantization | Tokens/sec | RAM Usage |
|-------|-------------|------------|-----------|
| Llama 3.1 8B | Q4 | 18-25 | ~5 GB |
| Qwen 2.5 14B | Q4 | 10-15 | ~8 GB |
| DeepSeek R1 32B | Q4 | 5-8 | ~20 GB |

### M4 Pro (48-64GB RAM)

| Model | Quantization | Tokens/sec | RAM Usage |
|-------|-------------|------------|-----------|
| Llama 3.1 8B | Q4 | 35-45 | ~5 GB |
| Qwen 2.5 14B | Q4 | 22-30 | ~8 GB |
| DeepSeek R1 32B | Q4 | 11-14 | ~20 GB |
| Llama 3.1 70B | Q4 | 5-8 | ~40 GB |

---

## Sources

- [Apple MLX Research - Exploring LLMs on M5](https://machinelearning.apple.com/research/exploring-llms-mlx-m5)
- [Mac Mini M4 DeepSeek R1 Benchmarks](https://like2byte.com/mac-mini-m4-deepseek-r1-ai-benchmarks/)
- [Production-Grade Local LLM Inference on Apple Silicon (arXiv)](https://arxiv.org/abs/2511.05502)
- [Best Mac Mini for AI in 2026](https://www.marc0.dev/en/blog/best-mac-mini-for-ai-2026-local-llm-agent-setup-guide-1770718504817)
- [Mac Mini M4 Local LLM Server Guide](https://like2byte.com/mac-mini-m4-local-llm-server-agency/)
- [LM Studio + Claude Code Integration](https://lmstudio.ai/blog/claudecode)
- [Run Claude Code with Local Models](https://medium.com/@luongnv89/run-claude-code-on-local-cloud-models-in-5-minutes-ollama-openrouter-llama-cpp-6dfeaee03cda)
- [AI CLI Switchboard for Apple Silicon](https://github.com/PatchedReality/ai-cli-switchboard)
- [macos-automator-mcp](https://github.com/steipete/macos-automator-mcp)
- [automation-mcp](https://github.com/ashwwwin/automation-mcp)
- [apple-mcp](https://github.com/supermemoryai/apple-mcp)
- [MacPilot MCP Server Guide](https://skywork.ai/skypage/en/macos-automation-guide/1981243385877594112)
- [Mac Studio Headless Server Config](https://github.com/anurmatov/mac-studio-server)
- [macsvcs - Disable Unnecessary macOS Services](https://github.com/hyuni/macsvcs)
- [OpenClaw (Clawdbot) Complete Guide](https://www.jitendrazaa.com/blog/ai/clawdbot-complete-guide-open-source-ai-assistant-2026/)
- [OpenClaw Wikipedia](https://en.wikipedia.org/wiki/OpenClaw)
- [Headless Mac Server for AI](https://chawlaharshit.medium.com/how-i-turned-my-mac-into-a-headless-server-my-always-on-setup-for-ai-monitoring-and-automation-aa9a8ff9aeff)
- [pmset Reference](https://www.dssw.co.uk/reference/pmset/)
- [Ollama Native vs Docker Benchmark](https://www.vchalyi.com/blog/2025/ollama-performance-benchmark-macos/)
- [Apple MLX vs NVIDIA Comparison](https://www.markus-schall.de/en/2025/11/apple-mlx-vs-nvidia-how-local-ki-inference-works-on-the-mac/)
