/**
 * Autonomy tools — MCP-exposed watchdog, audit log, and scheduled maintenance.
 * Also registers MCP Resources (system state) and Prompts (common workflows).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { startWatchdog, stopWatchdog, getWatchdogStatus } from "../services/watchdog.js";
import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const AUDIT_FILE = join(homedir(), ".optimac", "audit.jsonl");

export function registerAutonomyTools(server: McpServer): void {

    // ---- WATCHDOG START ----
    server.registerTool(
        "optimac_watchdog_start",
        {
            title: "Start Watchdog",
            description: "Start the background watchdog that monitors memory pressure and AI stack health on a configurable interval. Auto-purges at critical memory.",
            inputSchema: {
                interval_minutes: z.number().min(1).max(1440).optional().describe("Check interval in minutes (default: from config, typically 360 = 6h)"),
            },
            annotations: { readOnlyHint: false },
        },
        async ({ interval_minutes }) => {
            const intervalMs = interval_minutes ? interval_minutes * 60 * 1000 : undefined;
            const status = startWatchdog(intervalMs);
            return {
                content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
            };
        }
    );

    // ---- WATCHDOG STOP ----
    server.registerTool(
        "optimac_watchdog_stop",
        {
            title: "Stop Watchdog",
            description: "Stop the background watchdog.",
            inputSchema: {},
            annotations: { readOnlyHint: false },
        },
        async () => {
            const status = stopWatchdog();
            return {
                content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
            };
        }
    );

    // ---- WATCHDOG STATUS ----
    server.registerTool(
        "optimac_watchdog_status",
        {
            title: "Watchdog Status",
            description: "Get current watchdog status: running state, interval, checks performed, and auto-actions taken.",
            inputSchema: {},
            annotations: { readOnlyHint: true },
        },
        async () => {
            const status = getWatchdogStatus();
            return {
                content: [{ type: "text" as const, text: JSON.stringify(status, null, 2) }],
            };
        }
    );

    // ---- AUDIT LOG READ ----
    server.registerTool(
        "optimac_audit_read",
        {
            title: "Read Audit Log",
            description: "Read the most recent entries from the OptiMac audit log (~/.optimac/audit.jsonl). Returns structured tool execution history.",
            inputSchema: {
                limit: z.number().min(1).max(500).optional().describe("Number of entries to return (default 50, from end)"),
                tool_filter: z.string().optional().describe("Filter entries by tool name (e.g., 'watchdog', 'optimac_purge_memory')"),
            },
            annotations: { readOnlyHint: true },
        },
        async ({ limit, tool_filter }) => {
            const maxEntries = limit ?? 50;

            if (!existsSync(AUDIT_FILE)) {
                return {
                    content: [{ type: "text" as const, text: JSON.stringify({ entries: [], message: "No audit log yet. Run some tools or start the watchdog." }, null, 2) }],
                };
            }

            try {
                const raw = readFileSync(AUDIT_FILE, "utf-8");
                let entries = raw
                    .split("\n")
                    .filter(Boolean)
                    .map((line) => {
                        try { return JSON.parse(line); }
                        catch { return null; }
                    })
                    .filter(Boolean);

                if (tool_filter) {
                    entries = entries.filter((e: { tool?: string }) => e.tool?.includes(tool_filter));
                }

                // Return last N entries (most recent)
                entries = entries.slice(-maxEntries);

                return {
                    content: [{
                        type: "text" as const,
                        text: JSON.stringify({
                            totalEntries: entries.length,
                            file: AUDIT_FILE,
                            entries,
                        }, null, 2),
                    }],
                };
            } catch (e) {
                return {
                    content: [{ type: "text" as const, text: JSON.stringify({ error: `Failed to read audit log: ${e instanceof Error ? e.message : e}` }, null, 2) }],
                    isError: true,
                };
            }
        }
    );

    // ---- MCP RESOURCE: System Health Summary ----
    server.resource(
        "system-health",
        "optimac://system/health",
        { description: "Live system health summary: memory, AI stack, watchdog status" },
        async () => {
            const watchdog = getWatchdogStatus();
            const summary = {
                watchdog,
                lastUpdated: new Date().toISOString(),
                tip: "Use optimac_system_overview for full hardware details, or optimac_memory_status for memory specifics.",
            };
            return {
                contents: [{
                    uri: "optimac://system/health",
                    text: JSON.stringify(summary, null, 2),
                    mimeType: "application/json",
                }],
            };
        }
    );

    // ---- MCP RESOURCE: Config ----
    server.resource(
        "config",
        "optimac://config",
        { description: "Current OptiMac configuration from ~/.optimac/config.json" },
        async () => {
            const configPath = join(homedir(), ".optimac", "config.json");
            let text = "{}";
            if (existsSync(configPath)) {
                text = readFileSync(configPath, "utf-8");
            }
            return {
                contents: [{
                    uri: "optimac://config",
                    text,
                    mimeType: "application/json",
                }],
            };
        }
    );

    // ---- MCP RESOURCE: Audit Trail ----
    server.resource(
        "audit-log",
        "optimac://audit/recent",
        { description: "Recent audit log entries (last 20)" },
        async () => {
            if (!existsSync(AUDIT_FILE)) {
                return { contents: [{ uri: "optimac://audit/recent", text: "[]", mimeType: "application/json" }] };
            }
            const raw = readFileSync(AUDIT_FILE, "utf-8");
            const entries = raw.split("\n").filter(Boolean).slice(-20);
            return {
                contents: [{
                    uri: "optimac://audit/recent",
                    text: `[${entries.join(",")}]`,
                    mimeType: "application/json",
                }],
            };
        }
    );

    // ---- MCP PROMPTS ----

    server.prompt(
        "optimize-for-inference",
        "Step-by-step guide to prepare this Mac for maximum AI inference performance",
        () => ({
            messages: [{
                role: "user" as const,
                content: {
                    type: "text" as const,
                    text: `Please optimize this Mac for AI inference by running these steps in order:

1. Run optimac_system_overview to see current state
2. Run optimac_models_running to see what's loaded
3. Run optimac_power_optimize to set power for always-on
4. Run optimac_reduce_ui_overhead to free GPU
5. Run optimac_disable_spotlight to reduce I/O
6. Run optimac_debloat with preset="moderate"
7. Run optimac_purge_memory to reclaim pages
8. Run optimac_memory_status to confirm improvement
9. Run optimac_watchdog_start to enable monitoring

Report each step's result and the total memory freed.`,
                },
            }],
        })
    );

    server.prompt(
        "safe-model-swap",
        {
            model: z.string().optional().describe("Model to swap to"),
            runtime: z.string().optional().describe("Runtime: ollama or mlx"),
        },
        ({ model, runtime }) => ({
            messages: [{
                role: "user" as const,
                content: {
                    type: "text" as const,
                    text: `Please safely swap the currently loaded model to ${model || "[specify model]"} on ${runtime || "ollama"}:

1. Run optimac_models_running to see what's currently loaded
2. Run optimac_model_ram_check with the new model's size
3. If it fits, run optimac_model_unload to free current model
4. Run optimac_purge_memory to reclaim pages
5. Run optimac_model_serve with the new model
6. Run optimac_model_chat with a test prompt to verify
7. Report the swap result with before/after RAM usage`,
                },
            }],
        })
    );

    server.prompt(
        "system-health-check",
        "Run a comprehensive system health check with recommendations",
        () => ({
            messages: [{
                role: "user" as const,
                content: {
                    type: "text" as const,
                    text: `Run a comprehensive health check and provide recommendations:

1. Run optimac_system_overview for full system snapshot
2. Run optimac_ai_stack_status to check all AI services
3. Run optimac_memory_pressure_check with dry_run=true
4. Run optimac_watchdog_status to check monitoring
5. Run optimac_audit_read with limit=10 for recent activity

Based on the results, provide:
- Current system health grade (A-F)
- Memory pressure assessment
- AI stack status summary
- Top 3 recommendations for improvement`,
                },
            }],
        })
    );
}
