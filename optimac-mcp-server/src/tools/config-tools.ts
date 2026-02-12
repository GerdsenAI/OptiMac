/**
 * Configuration management tools.
 * Read, modify, and reset OptiMac settings.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { loadConfig, saveConfig, type OptiMacConfig } from "../services/config.js";

export function registerConfigTools(server: McpServer): void {
  // ---- GET CONFIG ----
  server.registerTool(
    "optimac_config_get",
    {
      title: "Get Configuration",
      description: `Read the current OptiMac configuration from ~/.optimac/config.json.

Shows all settings including protected processes, memory thresholds, AI stack ports, disabled services, etc.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const config = loadConfig();
      return { content: [{ type: "text", text: JSON.stringify(config, null, 2) }] };
    }
  );

  // ---- SET CONFIG VALUE ----
  server.registerTool(
    "optimac_config_set",
    {
      title: "Set Configuration Value",
      description: `Modify a specific OptiMac configuration value.

Args:
  - key: Configuration key (e.g., "memoryWarningThreshold", "autoKillAtCritical")
  - value: New value (type must match the key's expected type)

Available keys:
  - memoryWarningThreshold: number (0.0-1.0), default 0.75
  - memoryCriticalThreshold: number (0.0-1.0), default 0.90
  - autoKillAtCritical: boolean, default true
  - maxProcessRSSMB: number, default 2048
  - maintenanceIntervalSec: number, default 21600

For array values (protectedProcesses, disabledServices), use optimac_config_add/remove.`,
      inputSchema: {
        key: z.enum([
          "memoryWarningThreshold",
          "memoryCriticalThreshold",
          "autoKillAtCritical",
          "maxProcessRSSMB",
          "maintenanceIntervalSec",
        ]).describe("Configuration key"),
        value: z.union([z.number(), z.boolean()]).describe("New value"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ key, value }) => {
      const config = loadConfig();

      // Type checking
      const expectedTypes: Record<string, string> = {
        memoryWarningThreshold: "number",
        memoryCriticalThreshold: "number",
        autoKillAtCritical: "boolean",
        maxProcessRSSMB: "number",
        maintenanceIntervalSec: "number",
      };

      if (typeof value !== expectedTypes[key]) {
        return {
          content: [{
            type: "text",
            text: `Error: ${key} expects ${expectedTypes[key]}, got ${typeof value}`,
          }],
          isError: true,
        };
      }

      // Validation
      if (key === "memoryWarningThreshold" || key === "memoryCriticalThreshold") {
        if (typeof value === "number" && (value < 0 || value > 1)) {
          return {
            content: [{ type: "text", text: "Error: threshold must be between 0.0 and 1.0" }],
            isError: true,
          };
        }
      }

      (config as unknown as Record<string, unknown>)[key] = value;
      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ status: "updated", key, value, saved: true }, null, 2),
        }],
      };
    }
  );

  // ---- ADD TO PROTECTED PROCESSES ----
  server.registerTool(
    "optimac_config_protect_process",
    {
      title: "Add Protected Process",
      description: `Add a process name to the protected list. Protected processes cannot be auto-killed during memory pressure events.

Args:
  - process_name: Name or substring to match (e.g., "my-custom-agent")`,
      inputSchema: {
        process_name: z.string().min(1).describe("Process name or substring to protect"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ process_name }) => {
      const config = loadConfig();

      if (config.protectedProcesses.includes(process_name)) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ status: "already_protected", process: process_name }, null, 2),
          }],
        };
      }

      config.protectedProcesses.push(process_name);
      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "added",
            process: process_name,
            protectedList: config.protectedProcesses,
          }, null, 2),
        }],
      };
    }
  );

  // ---- REMOVE FROM PROTECTED PROCESSES ----
  server.registerTool(
    "optimac_config_unprotect_process",
    {
      title: "Remove Protected Process",
      description: `Remove a process name from the protected list. The process will be eligible for auto-kill during critical memory pressure.

Args:
  - process_name: Exact name to remove from protection`,
      inputSchema: {
        process_name: z.string().min(1).describe("Process name to unprotect"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ process_name }) => {
      const config = loadConfig();
      const before = config.protectedProcesses.length;
      config.protectedProcesses = config.protectedProcesses.filter((p) => p !== process_name);

      if (config.protectedProcesses.length === before) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ status: "not_found", process: process_name }, null, 2),
          }],
        };
      }

      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "removed",
            process: process_name,
            protectedList: config.protectedProcesses,
          }, null, 2),
        }],
      };
    }
  );

  // ---- SET AI STACK PORT ----
  server.registerTool(
    "optimac_config_set_port",
    {
      title: "Set AI Stack Port",
      description: `Configure the port for an AI inference service. Used for health checks and management.

Args:
  - service: "ollama" | "lmstudio" | "mlx"
  - port: Port number (1024-65535)`,
      inputSchema: {
        service: z.enum(["ollama", "lmstudio", "mlx"]).describe("AI service name"),
        port: z.number().int().min(1024).max(65535).describe("Port number"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ service, port }) => {
      const config = loadConfig();
      config.aiStackPorts[service] = port;
      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "updated",
            service,
            port,
            allPorts: config.aiStackPorts,
          }, null, 2),
        }],
      };
    }
  );

  // ---- DEBLOAT PRESET ----
  server.registerTool(
    "optimac_debloat",
    {
      title: "Apply Debloat Preset",
      description: `Apply a debloat preset to disable unnecessary macOS services. This is the "nuke the bloat" button.

Presets:
  - minimal: Disable Siri, Notification Center, iCloud sync only
  - moderate: + Photo analysis, media analysis, suggestions, Handoff
  - aggressive: + Location services, App Store auto-updates, Time Machine

Each preset builds on the previous. All are reversible with optimac_enable_service.`,
      inputSchema: {
        preset: z.enum(["minimal", "moderate", "aggressive"]).describe("Debloat level"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ preset }) => {
      const minimal = [
        "com.apple.Siri.agent",
        "com.apple.notificationcenterui.agent",
        "com.apple.bird",
      ];

      const moderate = [
        ...minimal,
        "com.apple.photoanalysisd",
        "com.apple.mediaanalysisd",
        "com.apple.suggestd",
        "com.apple.assistantd",
        "com.apple.parsec-fbf",
        "com.apple.knowledge-agent",
      ];

      const aggressive = [
        ...moderate,
        "com.apple.locationd",
        "com.apple.AirPlayXPCHelper",
        "com.apple.iCloudNotificationAgent",
        "com.apple.softwareupdated",
      ];

      const services = preset === "minimal" ? minimal
        : preset === "moderate" ? moderate
        : aggressive;

      const results: Record<string, string> = {};

      for (const svc of services) {
        const uid = await import("node:child_process")
          .then((cp) => cp.execSync("id -u").toString().trim());

        const result = await import("../services/shell.js")
          .then((sh) => sh.runCommand(
            "launchctl",
            ["disable", `user/${uid}/${svc}`],
            { shell: false }
          ));

        results[svc] = result.exitCode === 0 ? "disabled" : result.stderr;
      }

      // Also disable Spotlight for moderate+
      if (preset !== "minimal") {
        const mdutil = await import("../services/shell.js")
          .then((sh) => sh.runCommand("sudo", ["mdutil", "-a", "-i", "off"], { shell: true }));
        results["spotlight"] = mdutil.exitCode === 0 ? "disabled" : mdutil.stderr;
      }

      // Save to config
      const config = loadConfig();
      config.disabledServices = [...new Set([...config.disabledServices, ...services])];
      saveConfig(config);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "complete",
            preset,
            servicesDisabled: Object.keys(results).length,
            results,
          }, null, 2),
        }],
      };
    }
  );
}
