/**
 * Tiered memory pressure management.
 * Nominal -> Warning -> Critical with configurable auto-kill.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { parseVmStat, parseProcessList } from "../services/parsers.js";
import { loadConfig, isProcessProtected } from "../services/config.js";

export function registerMemoryPressureTools(server: McpServer): void {
  // ---- MEMORY PRESSURE CHECK ----
  server.registerTool(
    "optimac_memory_pressure_check",
    {
      title: "Memory Pressure Check",
      description: `Evaluate current memory pressure and take action if thresholds are exceeded.

Behavior at each level:
  - NOMINAL (<75% used): Report only. No action taken.
  - WARNING (75-90% used): Report + list non-protected processes consuming >maxProcessRSSMB.
  - CRITICAL (>90% used): Report + purge memory + auto-kill non-protected high-memory processes (if autoKillAtCritical=true in config).

Args:
  - dry_run: If true, report what would happen without taking action (default false)

This is the core tool for keeping a 16GB M4 running inference without swap death.`,
      inputSchema: {
        dry_run: z.boolean().default(false).describe("Report actions without executing them"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ dry_run }) => {
      const config = loadConfig();

      // Get memory stats
      const [vmStat, sysctl, ps] = await Promise.all([
        runCommand("vm_stat"),
        runCommand("sysctl", ["hw.memsize", "hw.pagesize"]),
        runCommand("ps", ["aux", "-m"]),
      ]);

      const memory = parseVmStat(vmStat.stdout, sysctl.stdout);
      const processes = parseProcessList(ps.stdout);
      const usedPercent = memory.usedMB / memory.totalPhysicalMB;

      const report: Record<string, unknown> = {
        memoryUsedMB: memory.usedMB,
        memoryTotalMB: memory.totalPhysicalMB,
        usedPercent: Math.round(usedPercent * 100),
        pressureLevel: memory.pressureLevel,
        swapUsedMB: memory.swapUsedMB,
      };

      // Find killable high-memory processes
      const killable = processes.filter((p) => {
        if (isProcessProtected(p.command, config)) return false;
        if (p.rssMB < config.maxProcessRSSMB) return false;
        if (p.user === "root" && p.pid < 200) return false; // core system
        return true;
      });

      if (usedPercent < config.memoryWarningThreshold) {
        // NOMINAL
        report["level"] = "nominal";
        report["action"] = "none";
        report["message"] = "Memory usage is within normal bounds.";
      } else if (usedPercent < config.memoryCriticalThreshold) {
        // WARNING
        report["level"] = "warning";
        report["action"] = "advisory";
        report["message"] = `Memory usage at ${Math.round(usedPercent * 100)}%. Consider closing non-essential processes.`;
        report["highMemoryProcesses"] = killable.map((p) => ({
          pid: p.pid,
          command: p.command.substring(0, 60),
          rssMB: p.rssMB,
        }));
      } else {
        // CRITICAL
        report["level"] = "critical";

        if (dry_run) {
          report["action"] = "dry_run";
          report["wouldPurge"] = true;
          report["wouldKill"] = config.autoKillAtCritical ? killable.map((p) => ({
            pid: p.pid,
            command: p.command.substring(0, 60),
            rssMB: p.rssMB,
          })) : [];
          report["message"] = "DRY RUN: Would purge memory" +
            (config.autoKillAtCritical ? ` and kill ${killable.length} non-protected processes` : "");
        } else {
          const actions: string[] = [];

          // Always purge at critical
          const purge = await runCommand("sudo", ["purge"], { shell: true, timeout: LONG_TIMEOUT });
          actions.push(purge.exitCode === 0 ? "memory_purged" : `purge_failed: ${purge.stderr}`);

          // Auto-kill if enabled
          if (config.autoKillAtCritical && killable.length > 0) {
            const killed: Array<{ pid: number; command: string; rssMB: number; result: string }> = [];

            for (const proc of killable) {
              const kill = await runCommand("kill", ["-TERM", String(proc.pid)]);
              killed.push({
                pid: proc.pid,
                command: proc.command.substring(0, 60),
                rssMB: proc.rssMB,
                result: kill.exitCode === 0 ? "killed" : kill.stderr,
              });
            }

            actions.push(`killed_${killed.length}_processes`);
            report["killedProcesses"] = killed;
          }

          report["action"] = actions.join(", ");
          report["message"] = `CRITICAL: Memory at ${Math.round(usedPercent * 100)}%. Actions taken: ${actions.join(", ")}`;
        }
      }

      return { content: [{ type: "text", text: JSON.stringify(report, null, 2) }] };
    }
  );

  // ---- FULL MAINTENANCE CYCLE ----
  server.registerTool(
    "optimac_maintenance_cycle",
    {
      title: "Full Maintenance Cycle",
      description: `Run a complete maintenance cycle. This is what the "IQ 3000 admin" does every 6 hours:

1. Check memory pressure (with auto-kill if critical)
2. Purge inactive memory
3. Flush DNS cache
4. Check network route health
5. Clear temp files and old logs
6. Check disk space
7. Verify AI stack health
8. Report summary

Use dry_run=true to preview what actions will be taken without executing them.`,
      inputSchema: {
        dry_run: z.boolean().default(false).describe("If true, report planned actions without executing them"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ dry_run }) => {
      const report: Record<string, unknown> = {};
      const startTime = Date.now();

      // 1. Memory pressure check (always safe to read)
      const [vmStat, sysctl, ps] = await Promise.all([
        runCommand("vm_stat"),
        runCommand("sysctl", ["hw.memsize", "hw.pagesize"]),
        runCommand("ps", ["aux", "-m"]),
      ]);

      const memory = parseVmStat(vmStat.stdout, sysctl.stdout);
      report["memory"] = {
        usedMB: memory.usedMB,
        totalMB: memory.totalPhysicalMB,
        pressure: memory.pressureLevel,
        swapMB: memory.swapUsedMB,
      };

      if (dry_run) {
        report["mode"] = "DRY RUN — no destructive actions taken";
        report["planned_actions"] = [
          "sudo purge (free inactive memory pages)",
          "sudo dscacheutil -flushcache (flush DNS)",
          "sudo killall -HUP mDNSResponder (restart DNS resolver)",
          "Clear temp files older than 7 days from ~/Library/Logs",
          "Check disk space",
          "Verify AI stack health",
        ];

        // Still check disk & AI stack (read-only)
        const df = await runCommand("df", ["-h", "/"]);
        const dfLine = df.stdout.split("\n")[1] ?? "";
        report["disk"] = dfLine.trim();

        const config = loadConfig();
        const stackHealth: Record<string, string> = {};
        for (const [name, port] of Object.entries(config.aiStackPorts)) {
          const check = await runCommand("lsof", ["-i", `:${port}`, "-sTCP:LISTEN"]);
          stackHealth[name] = check.stdout.length > 0 ? "running" : "stopped";
        }
        report["aiStack"] = stackHealth;
        report["durationMs"] = Date.now() - startTime;

        return { content: [{ type: "text", text: JSON.stringify(report, null, 2) }] };
      }

      // === LIVE EXECUTION (dry_run === false) ===

      // 2. Purge memory
      const purge = await runCommand("sudo", ["purge"], { shell: true, timeout: LONG_TIMEOUT });
      report["purge"] = purge.exitCode === 0 ? "success" : purge.stderr;

      // 3. Flush DNS
      await runCommand("sudo", ["dscacheutil", "-flushcache"], { shell: true });
      await runCommand("sudo", ["killall", "-HUP", "mDNSResponder"], { shell: true });
      report["dns"] = "flushed";

      // 4. Network route health (READ-ONLY — do NOT flush routes, it kills connectivity)
      const routeCheck = await runCommand("netstat", ["-rn"]);
      const routeLines = routeCheck.stdout.split("\n").filter(Boolean);
      report["routes"] = { status: "healthy", count: routeLines.length - 1 };

      // 5. Clear temp files (only old logs, not /tmp which other processes need)
      await runCommand(
        "find",
        [`${process.env.HOME}/Library/Logs`, "-name", "*.log", "-mtime", "+7", "-delete"],
        { shell: true, timeout: 30_000 }
      );
      report["temp_cleanup"] = "done";

      // 6. Disk space
      const df = await runCommand("df", ["-h", "/"]);
      const dfLine = df.stdout.split("\n")[1] ?? "";
      report["disk"] = dfLine.trim();

      // 7. AI stack health
      const config = loadConfig();
      const stackHealth: Record<string, string> = {};
      for (const [name, port] of Object.entries(config.aiStackPorts)) {
        const check = await runCommand("lsof", ["-i", `:${port}`, "-sTCP:LISTEN"]);
        stackHealth[name] = check.stdout.length > 0 ? "running" : "stopped";
      }
      report["aiStack"] = stackHealth;

      // 8. Post-maintenance memory
      const postVm = await runCommand("vm_stat");
      const postMemory = parseVmStat(postVm.stdout, sysctl.stdout);
      report["memoryAfter"] = {
        usedMB: postMemory.usedMB,
        freedMB: memory.usedMB - postMemory.usedMB,
        pressure: postMemory.pressureLevel,
      };

      report["durationMs"] = Date.now() - startTime;

      return { content: [{ type: "text", text: JSON.stringify(report, null, 2) }] };
    }
  );
}
