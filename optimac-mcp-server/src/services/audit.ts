/**
 * Audit log service — persistent, structured logging for all tool executions.
 * Each MCP tool call can log its invocation, result, and timing here.
 * Stored as JSON Lines (JSONL) at ~/.optimac/audit.jsonl, with automatic rotation.
 */

import { appendFileSync, existsSync, mkdirSync, renameSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const OPTIMAC_DIR = join(homedir(), ".optimac");
const AUDIT_FILE = join(OPTIMAC_DIR, "audit.jsonl");
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB before rotation
const MAX_ROTATIONS = 5;

export interface AuditEntry {
    timestamp: string;
    tool: string;
    args?: Record<string, unknown>;
    result: "success" | "error" | "partial";
    durationMs?: number;
    errorType?: string;
    detail?: string;
}

function ensureDir(): void {
    if (!existsSync(OPTIMAC_DIR)) {
        mkdirSync(OPTIMAC_DIR, { recursive: true });
    }
}

/** Rotate audit.jsonl -> audit.1.jsonl -> audit.2.jsonl, etc. */
function rotateIfNeeded(): void {
    try {
        if (!existsSync(AUDIT_FILE)) return;
        const stat = statSync(AUDIT_FILE);
        if (stat.size < MAX_FILE_SIZE) return;

        // Shift existing rotations
        for (let i = MAX_ROTATIONS - 1; i >= 1; i--) {
            const from = join(OPTIMAC_DIR, `audit.${i}.jsonl`);
            const to = join(OPTIMAC_DIR, `audit.${i + 1}.jsonl`);
            if (existsSync(from)) {
                renameSync(from, to);
            }
        }
        renameSync(AUDIT_FILE, join(OPTIMAC_DIR, "audit.1.jsonl"));
    } catch (e) {
        console.error("[optimac] audit rotation failed:", e instanceof Error ? e.message : e);
    }
}

/**
 * Log an audit entry to ~/.optimac/audit.jsonl
 * Non-blocking — errors are swallowed to avoid breaking tool execution.
 */
export function auditLog(entry: AuditEntry): void {
    try {
        ensureDir();
        rotateIfNeeded();
        const line = JSON.stringify({ ...entry, timestamp: entry.timestamp || new Date().toISOString() }) + "\n";
        appendFileSync(AUDIT_FILE, line, "utf-8");
    } catch (e) {
        console.error("[optimac] audit log write failed:", e instanceof Error ? e.message : e);
    }
}

/**
 * Helper to wrap a tool handler with audit logging.
 * Captures timing, result status, and error details.
 */
export function withAudit<T>(
    toolName: string,
    args: Record<string, unknown>,
    handler: () => Promise<T>
): Promise<T> {
    const start = Date.now();
    return handler()
        .then((result) => {
            auditLog({
                timestamp: new Date().toISOString(),
                tool: toolName,
                args,
                result: "success",
                durationMs: Date.now() - start,
            });
            return result;
        })
        .catch((err: unknown) => {
            auditLog({
                timestamp: new Date().toISOString(),
                tool: toolName,
                args,
                result: "error",
                durationMs: Date.now() - start,
                errorType: err instanceof Error ? err.constructor.name : "unknown",
                detail: err instanceof Error ? err.message : String(err),
            });
            throw err;
        });
}
