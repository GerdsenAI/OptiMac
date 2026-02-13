/**
 * Watchdog service — background interval that monitors system health
 * and takes corrective action when thresholds are exceeded.
 *
 * Features:
 * - Periodic memory pressure check (configurable interval)
 * - Auto-purge at critical memory pressure
 * - AI stack liveness checks
 * - Audit log integration
 *
 * Start with `startWatchdog()`, stop with `stopWatchdog()`.
 */

import { runCommand } from "./shell.js";
import { loadConfig } from "./config.js";
import { checkPort } from "./net.js";
import { auditLog } from "./audit.js";
import { parseVmStat } from "./parsers.js";

let watchdogInterval: ReturnType<typeof setInterval> | null = null;
let isRunning = false;

export interface WatchdogStatus {
    running: boolean;
    intervalMs: number;
    checksPerformed: number;
    lastCheck: string | null;
    autoActions: number;
}

let stats = {
    checksPerformed: 0,
    lastCheck: null as string | null,
    autoActions: 0,
};

/** Single watchdog check cycle */
async function watchdogCycle(): Promise<void> {
    const config = loadConfig();
    const now = new Date().toISOString();
    stats.checksPerformed++;
    stats.lastCheck = now;

    try {
        // 1. Memory pressure check
        const [vmStat, sysctl] = await Promise.all([
            runCommand("vm_stat"),
            runCommand("sysctl", ["hw.memsize", "hw.pagesize", "vm.swapusage"]),
        ]);

        if (vmStat.exitCode === 0 && sysctl.exitCode === 0) {
            const memory = parseVmStat(vmStat.stdout, sysctl.stdout);
            const usageRatio = memory.usedMB / memory.totalPhysicalMB;

            if (usageRatio >= config.memoryCriticalThreshold) {
                // Critical: auto-purge
                console.error(`[optimac] watchdog: CRITICAL memory pressure (${Math.round(usageRatio * 100)}% used). Purging.`);
                await runCommand("sudo", ["purge"], { timeout: 30000, sudo: true });
                stats.autoActions++;
                auditLog({
                    timestamp: now,
                    tool: "watchdog",
                    result: "success",
                    detail: `auto-purge at ${Math.round(usageRatio * 100)}% memory usage`,
                });
            } else if (usageRatio >= config.memoryWarningThreshold) {
                console.error(`[optimac] watchdog: WARNING memory pressure (${Math.round(usageRatio * 100)}% used).`);
                auditLog({
                    timestamp: now,
                    tool: "watchdog",
                    result: "partial",
                    detail: `warning at ${Math.round(usageRatio * 100)}% memory usage`,
                });
            }
        }

        // 2. AI stack liveness check
        const ports = config.aiStackPorts;
        for (const [runtime, port] of Object.entries(ports)) {
            const alive = await checkPort(port as number);
            if (!alive) {
                // Just log, don't auto-restart (could be intentionally stopped)
                auditLog({
                    timestamp: now,
                    tool: "watchdog",
                    result: "partial",
                    detail: `${runtime} not responding on port ${port}`,
                });
            }
        }
    } catch (e) {
        console.error("[optimac] watchdog cycle error:", e instanceof Error ? e.message : e);
        auditLog({
            timestamp: now,
            tool: "watchdog",
            result: "error",
            detail: e instanceof Error ? e.message : String(e),
        });
    }
}

/**
 * Start the background watchdog.
 * @param intervalMs - Check interval in milliseconds (default: from config maintenanceIntervalSec * 1000)
 */
export function startWatchdog(intervalMs?: number): WatchdogStatus {
    if (isRunning) {
        return getWatchdogStatus();
    }

    const config = loadConfig();
    const interval = intervalMs ?? config.maintenanceIntervalSec * 1000;

    watchdogInterval = setInterval(() => {
        watchdogCycle().catch((e) => {
            console.error("[optimac] watchdog cycle failed:", e instanceof Error ? e.message : e);
        });
    }, interval);

    isRunning = true;
    auditLog({
        timestamp: new Date().toISOString(),
        tool: "watchdog",
        result: "success",
        detail: `started with interval ${interval}ms`,
    });

    return {
        running: true,
        intervalMs: interval,
        ...stats,
    };
}

/** Stop the background watchdog. */
export function stopWatchdog(): WatchdogStatus {
    if (watchdogInterval) {
        clearInterval(watchdogInterval);
        watchdogInterval = null;
    }
    isRunning = false;

    auditLog({
        timestamp: new Date().toISOString(),
        tool: "watchdog",
        result: "success",
        detail: "stopped",
    });

    return getWatchdogStatus();
}

/** Get current watchdog status. */
export function getWatchdogStatus(): WatchdogStatus {
    const config = loadConfig();
    return {
        running: isRunning,
        intervalMs: config.maintenanceIntervalSec * 1000,
        ...stats,
    };
}
