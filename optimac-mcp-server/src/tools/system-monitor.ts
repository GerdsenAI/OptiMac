/**
 * System monitoring tools: memory, CPU, disk, thermal, processes.
 * All read-only. These are the eyes of OptiMac.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand } from "../services/shell.js";
import {
  parseVmStat,
  parseProcessList,
  parseDiskUsage,
  parsePowerMetrics,
  parsePMSet,
  type MemoryStats,
  type ProcessInfo,
  type DiskUsage,
} from "../services/parsers.js";
import { loadConfig } from "../services/config.js";

export function registerSystemMonitorTools(server: McpServer): void {
  // ---- MEMORY STATUS ----
  server.registerTool(
    "optimac_memory_status",
    {
      title: "Memory Status",
      description: `Get detailed memory statistics including physical RAM usage, swap, compressed memory, and pressure level.

Returns: totalPhysicalMB, usedMB, freeMB, activePages, wiredPages, compressedPages, swapUsedMB, pressureLevel (nominal/warning/critical).

On a 16GB M4, watch for pressureLevel. "warning" means >75% used, "critical" means >90% and swap is likely thrashing.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const [vmStat, sysctl] = await Promise.all([
        runCommand("vm_stat"),
        runCommand("sysctl", ["hw.memsize"]),
      ]);

      if (vmStat.exitCode !== 0) {
        return { content: [{ type: "text", text: `Error reading memory: ${vmStat.stderr}` }], isError: true };
      }

      const stats = parseVmStat(vmStat.stdout, sysctl.stdout);
      const config = loadConfig();

      const output = {
        ...stats,
        thresholds: {
          warningAt: `${Math.round(config.memoryWarningThreshold * 100)}%`,
          criticalAt: `${Math.round(config.memoryCriticalThreshold * 100)}%`,
          autoKillEnabled: config.autoKillAtCritical,
        },
      };

      return { content: [{ type: "text", text: JSON.stringify(output, null, 2) }] };
    }
  );

  // ---- TOP PROCESSES ----
  server.registerTool(
    "optimac_top_processes",
    {
      title: "Top Processes",
      description: `List top processes by memory or CPU usage. Shows PID, user, CPU%, MEM%, RSS in MB, and command.

Args:
  - sort_by: "memory" (default) or "cpu"
  - limit: number of processes to return (default 20, max 100)
  - show_protected: whether to mark protected processes in output (default true)

Use this to identify memory hogs before running optimac_kill_process.`,
      inputSchema: {
        sort_by: z.enum(["memory", "cpu"]).default("memory").describe("Sort by memory or CPU usage"),
        limit: z.number().int().min(1).max(100).default(20).describe("Max processes to return"),
        show_protected: z.boolean().default(true).describe("Mark protected processes"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ sort_by, limit, show_protected }) => {
      const sortFlag = sort_by === "cpu" ? "-r" : "-m";
      const result = await runCommand("ps", ["aux", "-r"]);

      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Error: ${result.stderr}` }], isError: true };
      }

      let processes = parseProcessList(result.stdout);

      if (sort_by === "cpu") {
        processes.sort((a, b) => b.cpuPercent - a.cpuPercent);
      }

      processes = processes.slice(0, limit);

      const config = loadConfig();
      const output = processes.map((p) => ({
        ...p,
        protected: show_protected
          ? config.protectedProcesses.some((pp) => p.command.toLowerCase().includes(pp.toLowerCase()))
          : undefined,
      }));

      return { content: [{ type: "text", text: JSON.stringify(output, null, 2) }] };
    }
  );

  // ---- DISK USAGE ----
  server.registerTool(
    "optimac_disk_usage",
    {
      title: "Disk Usage",
      description: `Show disk usage for all mounted volumes. Returns filesystem, size, used, available in MB, and usage percentage.

Critical for 16GB setups where swap lives on disk -- if the boot volume is >90% full, swap will fail and the system will freeze.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("df", ["-k"]);
      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Error: ${result.stderr}` }], isError: true };
      }

      const disks = parseDiskUsage(result.stdout).filter(
        (d) => !d.filesystem.startsWith("devfs") && !d.filesystem.startsWith("map")
      );

      return { content: [{ type: "text", text: JSON.stringify(disks, null, 2) }] };
    }
  );

  // ---- THERMAL STATUS ----
  server.registerTool(
    "optimac_thermal_status",
    {
      title: "Thermal Status",
      description: `Read CPU/GPU temperatures and throttling status using powermetrics.

Requires sudo. Returns CPU temperature (C), GPU temperature (C), and whether thermal throttling is active.

On Mac Mini M4, sustained inference at >95C will trigger thermal throttling and reduce throughput.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand(
        "sudo",
        ["powermetrics", "--samplers", "smc", "-i", "1000", "-n", "1"],
        { shell: true, timeout: 10_000 }
      );

      if (result.exitCode !== 0) {
        // Fallback: try without sudo
        const fallback = await runCommand("pmset", ["-g", "therm"]);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              note: "powermetrics requires sudo. Showing pmset thermal info instead.",
              raw: fallback.stdout,
            }, null, 2),
          }],
        };
      }

      const thermal = parsePowerMetrics(result.stdout);
      return { content: [{ type: "text", text: JSON.stringify(thermal, null, 2) }] };
    }
  );

  // ---- POWER SETTINGS ----
  server.registerTool(
    "optimac_power_settings",
    {
      title: "Power Settings",
      description: `Read current pmset power management settings. Shows sleep, displaysleep, disksleep, womp (Wake on LAN), autorestart, powernap, etc.

Use optimac_set_power to modify these settings.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("pmset", ["-g"]);
      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Error: ${result.stderr}` }], isError: true };
      }

      const settings = parsePMSet(result.stdout);
      return { content: [{ type: "text", text: JSON.stringify(settings, null, 2) }] };
    }
  );

  // ---- SYSTEM OVERVIEW (the big one) ----
  server.registerTool(
    "optimac_system_overview",
    {
      title: "System Overview",
      description: `Get a comprehensive system health snapshot in one call. Returns memory, top 5 processes, disk, power settings, uptime, and AI stack status.

This is the "dashboard" tool. Use it for a quick health check before making decisions. Combines multiple data sources into a single structured response.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const [vmStat, sysctl, ps, df, pmset, uptime, hostname] = await Promise.all([
        runCommand("vm_stat"),
        runCommand("sysctl", ["hw.memsize"]),
        runCommand("ps", ["aux", "-m"]),
        runCommand("df", ["-k"]),
        runCommand("pmset", ["-g"]),
        runCommand("uptime"),
        runCommand("hostname"),
      ]);

      const memory = parseVmStat(vmStat.stdout, sysctl.stdout);
      const processes = parseProcessList(ps.stdout).slice(0, 5);
      const disks = parseDiskUsage(df.stdout).filter(
        (d) => d.mountPoint === "/" || d.mountPoint.startsWith("/System/Volumes/Data")
      );
      const power = parsePMSet(pmset.stdout);

      // Check AI stack health
      const config = loadConfig();
      const stackStatus: Record<string, string> = {};

      for (const [name, port] of Object.entries(config.aiStackPorts)) {
        const check = await runCommand("lsof", ["-i", `:${port}`, "-sTCP:LISTEN"]);
        stackStatus[name] = check.stdout.length > 0 ? "running" : "stopped";
      }

      const overview = {
        hostname: hostname.stdout,
        uptime: uptime.stdout.trim(),
        memory: {
          totalMB: memory.totalPhysicalMB,
          usedMB: memory.usedMB,
          freeMB: memory.freeMB,
          compressedMB: Math.round(memory.compressedPages * 4096 / (1024 * 1024)),
          swapUsedMB: memory.swapUsedMB,
          pressureLevel: memory.pressureLevel,
        },
        topProcessesByMemory: processes.map((p) => ({
          pid: p.pid,
          command: p.command.substring(0, 60),
          rssMB: p.rssMB,
          cpuPercent: p.cpuPercent,
        })),
        disk: disks.map((d) => ({
          mount: d.mountPoint,
          usedPercent: d.usedPercent,
          availableMB: d.availableMB,
        })),
        power: {
          sleep: power["sleep"],
          autorestart: power["autorestart"],
          womp: power["womp"],
          powernap: power["powernap"],
        },
        aiStack: stackStatus,
      };

      return { content: [{ type: "text", text: JSON.stringify(overview, null, 2) }] };
    }
  );
}
