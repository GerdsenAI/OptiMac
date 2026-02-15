/**
 * Security tools: Application Firewall, audits, integrity checks.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import fs from "fs/promises";
import path from "path";
import os from "os";

export function registerSecurityTools(server: McpServer): void {
    // ---- SECURITY OVERVIEW ----
    server.registerTool(
        "optimac_sec_status",
        {
            title: "Security Status Overview",
            description: "Get status of macOS security features: SIP, Gatekeeper, FileVault, and Firewall.",
            inputSchema: {},
        },
        async () => {
            const results: Record<string, string> = {};

            // SIP
            const sip = await runCommand("csrutil", ["status"]);
            results["SIP"] = sip.stdout.trim() || sip.stderr;

            // Gatekeeper
            const gk = await runCommand("spctl", ["--status"]);
            results["Gatekeeper"] = gk.stdout.trim() || gk.stderr;

            // FileVault
            const fv = await runCommand("fdesetup", ["status"]);
            results["FileVault"] = fv.stdout.trim() || fv.stderr;

            // Firewall (requires sudo usually, but let's try reading prefs or checking socketfilterfw without sudo first?)
            // socketfilterfw usually works without sudo for --getglobalstate
            const fw = await runCommand("/usr/libexec/ApplicationFirewall/socketfilterfw", ["--getglobalstate"]);
            results["Firewall"] = fw.stdout.trim() || fw.stderr || "Needs sudo";

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify(results, null, 2),
                }],
            };
        }
    );

    // ---- FIREWALL CONTROL ----
    server.registerTool(
        "optimac_sec_firewall",
        {
            title: "Firewall Control",
            description: "Enable or disable the macOS Application Firewall.",
            inputSchema: {
                action: z.enum(["on", "off"]).describe("Turn firewall on or off"),
            },
            annotations: { destructiveHint: true },
        },
        async ({ action }) => {
            const result = await runCommand(
                "sudo",
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", action],
                { shell: true }
            );

            return {
                content: [{
                    type: "text",
                    text: result.exitCode === 0
                        ? `Firewall turned ${action}`
                        : `Failed (needs sudo): ${result.stderr}`,
                }],
            };
        }
    );

    // ---- OPEN PORTS AUDIT ----
    server.registerTool(
        "optimac_sec_audit_ports",
        {
            title: "Audit Open Ports",
            description: "Scan for open listening ports and highlight suspicious ones.",
            inputSchema: {},
        },
        async () => {
            const result = await runCommand("lsof", ["-i", "-P", "-n"]);
            if (result.exitCode !== 0) {
                return { content: [{ type: "text", text: `Error: ${result.stderr}` }], isError: true };
            }

            const lines = result.stdout.split("\n").filter((l) => l.includes("LISTEN"));
            const knownSafe = new Set([22, 53, 80, 443, 631, 5000, 5353, 8080, 8443, 11434, 1234]);
            const suspicious: string[] = [];

            for (const line of lines) {
                const parts = line.split(/\s+/);
                // COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
                // sshd 123 root 3u IPv6 0x... 0t0 TCP *:22 (LISTEN)
                if (parts.length >= 9) {
                    const portPart = parts[8].split(":").pop();
                    if (portPart) {
                        const port = parseInt(portPart, 10);
                        if (!isNaN(port) && !knownSafe.has(port) && port < 49152) {
                            suspicious.push(line);
                        }
                    }
                }
            }

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        totalListening: lines.length,
                        suspiciousCount: suspicious.length,
                        suspiciousEntries: suspicious,
                        allEntries: lines.slice(0, 50), // cap active output
                    }, null, 2),
                }],
            };
        }
    );

    // ---- MALWARE PATH CHECK ----
    server.registerTool(
        "optimac_sec_audit_malware",
        {
            title: "Malware Path Check",
            description: "Check common malware persistence locations (LaunchAgents, hidden folders).",
            inputSchema: {},
        },
        async () => {
            const home = os.homedir();
            const suspiciousPaths = [
                path.join(home, "Library", "LaunchAgents"),
                "/Library/LaunchAgents",
                "/Library/LaunchDaemons",
                path.join(home, ".mitmproxy"),
                path.join(home, ".proxy"),
                path.join(home, "Library", "Application Support", "com.pcv"),
                "/private/tmp/.hidden",
                path.join(home, ".local", "share", ".hidden"),
            ];

            const findings: string[] = [];
            let checkedCount = 0;

            for (const p of suspiciousPaths) {
                try {
                    const stats = await fs.stat(p);
                    checkedCount++;
                    if (stats.isDirectory()) {
                        // Check contents
                        const items = await fs.readdir(p);
                        for (const item of items) {
                            if (item.endsWith(".plist") && !item.toLowerCase().startsWith("com.apple")) {
                                findings.push(`[Suspicious Plist] ${path.join(p, item)}`);
                            }
                        }
                    } else {
                        // It's a file where we expected a dir or just exists
                        findings.push(`[Found] ${p}`);
                    }
                } catch (e) {
                    // Path doesn't exist, which is good
                }
            }

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        status: findings.length === 0 ? "clean" : "suspicious_items_found",
                        checkedLocations: checkedCount,
                        findings,
                    }, null, 2),
                }],
            };
        }
    );

    // ---- FAILED LOGINS AUDIT ----
    server.registerTool(
        "optimac_sec_audit_auth",
        {
            title: "Audit Failed Logins",
            description: "Search system logs for failed authentication attempts in the last hour.",
            inputSchema: {},
        },
        async () => {
            // log show --style compact --predicate 'eventMessage contains "authentication" OR eventMessage contains "failed"' --last 1h
            const predicate = 'eventMessage contains "authentication" OR eventMessage contains "failed" OR eventMessage contains "invalid"';
            const result = await runCommand(
                "log",
                ["show", "--style", "compact", "--predicate", predicate, "--last", "1h"],
                { timeout: 30000 }
            );

            if (result.exitCode !== 0) {
                return { content: [{ type: "text", text: `Log query failed: ${result.stderr}` }], isError: true };
            }

            const lines = result.stdout.split("\n");
            const failures = lines.filter((l) =>
                l.toLowerCase().includes("fail") ||
                l.toLowerCase().includes("invalid") ||
                l.toLowerCase().includes("deny")
            );

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        eventsFound: lines.length,
                        failureCount: failures.length,
                        failures: failures.slice(0, 20),
                    }, null, 2),
                }],
            };
        }
    );

    // ---- UNSIGNED PROCESSES ----
    server.registerTool(
        "optimac_sec_audit_unsigned",
        {
            title: "Unsigned Processes Audit",
            description: "Check running processes for unsigned binaries. Scans up to 50 processes with codesign verification.",
            inputSchema: {
                limit: z.number().optional().default(50).describe("Max processes to check"),
            },
        },
        async ({ limit }) => {
            // Get list of running processes with their paths
            const ps = await runCommand("ps", ["-axo", "pid,comm"], { timeout: 10000 });
            if (ps.exitCode !== 0) {
                return { content: [{ type: "text", text: `Failed to list processes: ${ps.stderr}` }], isError: true };
            }

            const lines = ps.stdout.split("\n").slice(1); // skip header
            const unsigned: Array<{ pid: string; name: string; path: string }> = [];
            let checked = 0;

            for (const line of lines) {
                if (checked >= limit) break;
                const trimmed = line.trim();
                if (!trimmed) continue;
                const parts = trimmed.split(/\s+/);
                const pid = parts[0];
                const exe = parts.slice(1).join(" ");
                if (!exe || !exe.startsWith("/")) continue;

                checked++;
                const verify = await runCommand("codesign", ["--verify", "--deep", exe], { timeout: 5000 });
                if (verify.exitCode !== 0) {
                    const name = exe.split("/").pop() || exe;
                    unsigned.push({ pid, name, path: exe });
                }
            }

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        checked,
                        unsignedCount: unsigned.length,
                        unsigned: unsigned.slice(0, 20),
                    }, null, 2),
                }],
            };
        }
    );

    // ---- CONNECTION AUDIT ----
    server.registerTool(
        "optimac_sec_audit_connections",
        {
            title: "Foreign Connection Audit",
            description: "Audit established network connections for foreign (non-local) IPs using lsof.",
            inputSchema: {},
        },
        async () => {
            const result = await runCommand("lsof", ["-i", "-P", "-n"], { timeout: 15000 });
            if (result.exitCode !== 0) {
                return { content: [{ type: "text", text: `lsof failed: ${result.stderr}` }], isError: true };
            }

            const localPrefixes = ["127.", "10.", "172.", "192.168.", "::1", "fe80"];
            const lines = result.stdout.split("\n");
            const established = lines.filter((l) => l.includes("ESTABLISHED"));
            const foreign: Array<{ process: string; remote: string }> = [];

            for (const conn of established) {
                const parts = conn.split(/\s+/);
                if (parts.length >= 9) {
                    const remote = parts[8];
                    const ip = remote.replace("->", "").split(":")[0];
                    if (ip && !localPrefixes.some((p) => ip.startsWith(p))) {
                        foreign.push({ process: parts[0], remote });
                    }
                }
            }

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        establishedConnections: established.length,
                        foreignConnections: foreign.length,
                        foreign: foreign.slice(0, 25),
                    }, null, 2),
                }],
            };
        }
    );
}
