#!/usr/bin/env node
/**
 * OptiMac MCP Server
 *
 * A comprehensive MCP server for Mac Mini M4 / M4 Pro AI inference optimization.
 * Controls system resources, manages AI inference stacks, handles memory pressure,
 * and performs automated maintenance -- all accessible via Claude Desktop or Claude Code.
 *
 * Transport: stdio (launched as subprocess by MCP client)
 * Config: ~/.optimac/config.json
 *
 * 46+ tools across 7 domains:
 *   - System Monitoring (6): memory, processes, disk, thermal, power, overview
 *   - System Control (13): purge, DNS, routes, power, power-optimize, spotlight, caches, set-dns, services, enable-service, network-reset, reduce-ui, kill-process
 *   - AI Stack (7): status, ollama start/stop/models, mlx start/stop, smart swap
 *   - Model Management (8): browse local models, ollama available, serve/load, unload, running models, model dir, RAM check, chat/inference
 *   - Model Tasks (6): cloud-to-edge bridge -- task delegation, code review, file generation, file editing, summarization, git commit
 *   - Memory Pressure (2): pressure check with tiered response, full maintenance cycle
 *   - Configuration (6): get/set config, protect/unprotect processes, ports, debloat presets
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
import { loadConfig } from "./services/config.js";

const VERSION = "2.0.0";

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

  console.error("All tools registered (46+ tools across 7 domains). Starting stdio transport...");

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("OptiMac MCP Server running via stdio. Ready for commands.");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
