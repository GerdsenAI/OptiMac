#!/usr/bin/env node
/**
 * OptiMac MCP Server
 *
 * A comprehensive MCP server for Mac Mini M4 / M4 Pro AI inference optimization.
 * Controls system resources, manages AI inference stacks, handles memory pressure,
 * and bridges local ↔ edge ↔ cloud inference as equal peers — accessible via any MCP client.
 *
 * Transport: stdio (launched as subprocess by MCP client)
 * Config: ~/.optimac/config.json
 *
 * 89 tools across 11 domains:
 *   - System Monitoring (8): memory, processes, disk, thermal, power, overview, battery-health, io-stats
 *   - System Control (23): purge, DNS, routes, power, power-optimize, spotlight, caches, set-dns, services, enable-service, network-reset, reduce-ui, kill-process, nvram-perf-mode, login-items, eject, lock, restart-service, trash, power-profile, debloat-reenable, rebuild-spotlight, optimize-homebrew
 *   - AI Stack (10): status, ollama start/stop/models, mlx start/stop, smart swap, gpu-stats, benchmark, quantize
 *   - Network Tools (7): connections, info, ping, speedtest, wifi, bluetooth, wol
 *   - Security Tools (7): status, firewall, port-audit, malware-audit, auth-audit, unsigned-processes, connection-audit
 *   - Model Management (9): browse local models, ollama available, serve/load, unload, running models, model dir get/set, RAM check, chat/inference
 *   - Model Tasks (9): bidirectional AI bridge -- task delegation, code review, file generation, file editing, summarization, git commit, cloud escalation, edge escalation, smart 3-tier routing
 *   - Edge-to-Edge (4): add/remove/list/test edge endpoints for LAN inference
 *   - Memory Pressure (2): pressure check with tiered response, full maintenance cycle
 *   - Configuration (6): get/set config, protect/unprotect processes, ports, debloat presets
 *   - Autonomy (4): watchdog start/stop/status, audit log reading
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerSystemMonitorTools } from "./tools/system-monitor.js";
import { registerSystemControlTools } from "./tools/system-control.js";
import { registerAIStackTools } from "./tools/ai-stack.js";
import { registerMemoryPressureTools } from "./tools/memory-pressure.js";
import { registerConfigTools } from "./tools/config-tools.js";
import { registerModelManagementTools } from "./tools/model-management.js";
import { registerModelTaskTools } from "./tools/model-tasks.js";
import { registerAutonomyTools } from "./tools/autonomy-tools.js";
import { registerEdgeTools } from "./tools/edge-tools.js";
import { registerNetworkTools } from "./tools/network-tools.js";
import { registerSecurityTools } from "./tools/security-tools.js";
import { loadConfig } from "./services/config.js";

const VERSION = "2.7.0";

async function main(): Promise<void> {
  // Initialize config on first run
  const config = loadConfig();

  // Log to stderr (stdout is reserved for MCP protocol)
  console.error(`OptiMac MCP Server v${VERSION}`);
  console.error(`Config loaded from ~/.optimac/config.json`);
  console.error(`Protected processes: ${config.protectedProcesses.length}`);
  console.error(`Memory thresholds: warning=${config.memoryWarningThreshold}, critical=${config.memoryCriticalThreshold}`);
  console.error(`Auto-kill at critical: ${config.autoKillAtCritical}`);
  console.error(`AI stack ports: ollama=${config.aiStackPorts.ollama}, lmstudio=${config.aiStackPorts.lmstudio}, mlx=${config.aiStackPorts.mlx}`);

  // Create MCP server
  const server = new McpServer({
    name: "optimac-mcp-server",
    version: VERSION,
  });

  // Register all tool domains
  registerSystemMonitorTools(server);
  registerSystemControlTools(server);
  registerAIStackTools(server);
  registerMemoryPressureTools(server);
  registerConfigTools(server);
  registerModelManagementTools(server);
  registerModelTaskTools(server);
  registerEdgeTools(server);
  registerAutonomyTools(server);
  registerNetworkTools(server);
  registerSecurityTools(server);

  const edgeCount = Object.keys(config.edgeEndpoints).length;
  console.error(`Edge endpoints configured: ${edgeCount}`);
  console.error("All tools registered (89 tools across 11 domains). Starting stdio transport...");

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("OptiMac MCP Server running via stdio. Ready for commands.");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
