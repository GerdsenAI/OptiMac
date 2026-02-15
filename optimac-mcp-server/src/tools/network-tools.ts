/**
 * Network tools: connections, speed test, Wi-Fi/BT toggles, WoL.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import dgram from "dgram";

export function registerNetworkTools(server: McpServer): void {
    // ---- ACTIVE CONNECTIONS ----
    server.registerTool(
        "optimac_net_connections",
        {
            title: "Active Connections",
            description: "List active network connections and listening ports using lsof.",
            inputSchema: {
                filter: z.enum(["all", "established", "listen"]).default("all").describe("Filter connections"),
                limit: z.number().default(20).describe("Max results to return"),
            },
        },
        async ({ filter, limit }) => {
            const result = await runCommand("lsof", ["-i", "-P", "-n"]);
            if (result.exitCode !== 0) {
                return { content: [{ type: "text", text: `Error: ${result.stderr}` }], isError: true };
            }

            let lines = result.stdout.split("\n").slice(1); // skip header
            if (filter === "established") {
                lines = lines.filter((l) => l.includes("ESTABLISHED"));
            } else if (filter === "listen") {
                lines = lines.filter((l) => l.includes("LISTEN"));
            }

            const count = lines.length;
            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        count,
                        connections: lines.slice(0, limit),
                    }, null, 2),
                }],
            };
        }
    );

    // ---- PUBLIC IP & GEO ----
    server.registerTool(
        "optimac_net_info",
        {
            title: "Public IP Info",
            description: "Get public IP address and geolocation info.",
            inputSchema: {},
        },
        async () => {
            const ipResult = await runCommand("curl", ["-s", "-m", "5", "ifconfig.me"]);
            const ip = ipResult.stdout.trim();

            if (!ip) {
                return { content: [{ type: "text", text: "Could not determine public IP" }], isError: true };
            }

            const geoResult = await runCommand("curl", ["-s", "-m", "5", `https://ipinfo.io/${ip}/json`]);
            let geo = {};
            try {
                geo = JSON.parse(geoResult.stdout);
            } catch (e) {
                // ignore parse error
            }

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({ ip, ...geo }, null, 2),
                }],
            };
        }
    );

    // ---- PING HOST ----
    server.registerTool(
        "optimac_net_ping",
        {
            title: "Ping Host",
            description: "Ping a host to check reachability and latency.",
            inputSchema: {
                host: z.string().describe("Hostname or IP to ping"),
                count: z.number().default(4).describe("Number of pings"),
            },
        },
        async ({ host, count }) => {
            const result = await runCommand("ping", ["-c", String(count), "-t", "5", host]);
            return {
                content: [{
                    type: "text",
                    text: result.stdout || result.stderr,
                }],
            };
        }
    );

    // ---- SPEED TEST ----
    server.registerTool(
        "optimac_net_speedtest",
        {
            title: "Speed Test",
            description: "Run a quick download speed test using Cloudflare (10MB).",
            inputSchema: {},
        },
        async () => {
            const url = "https://speed.cloudflare.com/__down?measId=0&bytes=10000000";
            const start = Date.now();
            const result = await runCommand("curl", ["-s", "-o", "/dev/null", "-w", "%{speed_download}", url], { timeout: 30000 });
            const elapsed = (Date.now() - start) / 1000;

            if (result.exitCode !== 0) {
                return { content: [{ type: "text", text: `Speed test failed: ${result.stderr}` }], isError: true };
            }

            const bps = parseFloat(result.stdout);
            const mbps = (bps * 8) / 1000000;

            return {
                content: [{
                    type: "text",
                    text: JSON.stringify({
                        downloadMbps: parseFloat(mbps.toFixed(2)),
                        timeSeconds: parseFloat(elapsed.toFixed(1)),
                        server: "Cloudflare",
                    }, null, 2),
                }],
            };
        }
    );

    // ---- WI-FI CONTROL ----
    server.registerTool(
        "optimac_net_wifi",
        {
            title: "Wi-Fi Control",
            description: "Get status or toggle Wi-Fi on/off.",
            inputSchema: {
                action: z.enum(["status", "on", "off"]).describe("Action to perform"),
            },
            annotations: { destructiveHint: true },
        },
        async ({ action }) => {
            // Detect Wi-Fi interface
            const hwPorts = await runCommand("networksetup", ["-listallhardwareports"]);
            let wifiDevice = "en0"; // fallback
            if (hwPorts.exitCode === 0) {
                const lines = hwPorts.stdout.split("\n");
                for (let i = 0; i < lines.length; i++) {
                    if (lines[i].includes("Hardware Port: Wi-Fi")) {
                        // Next line should be Device: enX
                        const deviceLine = lines[i + 1];
                        if (deviceLine && deviceLine.includes("Device: ")) {
                            wifiDevice = deviceLine.split("Device: ")[1].trim();
                        }
                        break;
                    }
                }
            }

            if (action === "status") {
                const result = await runCommand("networksetup", ["-getairportpower", wifiDevice]);
                return { content: [{ type: "text", text: result.stdout.trim() || result.stderr }] };
            }

            const state = action === "on" ? "On" : "Off";
            const result = await runCommand("networksetup", ["-setairportpower", wifiDevice, state]);
            return {
                content: [{
                    type: "text",
                    text: result.exitCode === 0
                        ? `Wi-Fi (${wifiDevice}) turned ${state}`
                        : `Failed: ${result.stderr}`,
                }],
            };
        }
    );

    // ---- BLUETOOTH CONTROL ----
    server.registerTool(
        "optimac_net_bluetooth",
        {
            title: "Bluetooth Control",
            description: "Get status or toggle Bluetooth on/off. Requires 'blueutil' (brew install blueutil).",
            inputSchema: {
                action: z.enum(["status", "on", "off"]).describe("Action to perform"),
            },
            annotations: { destructiveHint: true },
        },
        async ({ action }) => {
            const check = await runCommand("which", ["blueutil"]);
            if (check.exitCode !== 0) {
                return { content: [{ type: "text", text: "Error: blueutil not installed. Run 'brew install blueutil'." }], isError: true };
            }

            if (action === "status") {
                const result = await runCommand("blueutil", ["--power"]);
                const isOn = result.stdout.trim() === "1";
                return { content: [{ type: "text", text: isOn ? "Bluetooth: On" : "Bluetooth: Off" }] };
            }

            const state = action === "on" ? "1" : "0";
            const result = await runCommand("blueutil", ["--power", state]);
            return {
                content: [{
                    type: "text",
                    text: result.exitCode === 0 ? `Bluetooth turned ${action}` : `Failed: ${result.stderr}`,
                }],
            };
        }
    );

    // ---- WAKE ON LAN ----
    server.registerTool(
        "optimac_net_wol",
        {
            title: "Wake-on-LAN",
            description: "Send a Wake-on-LAN magic packet to a MAC address.",
            inputSchema: {
                mac: z.string().describe("MAC address (e.g. AA:BB:CC:DD:EE:FF)"),
            },
        },
        async ({ mac }) => {
            // Validate MAC
            const macClean = mac.replace(/[^0-9a-fA-F]/g, "");
            if (macClean.length !== 12) {
                return { content: [{ type: "text", text: "Invalid MAC address format" }], isError: true };
            }

            const buffer = Buffer.alloc(102);
            // Header: 6 bytes of FF
            for (let i = 0; i < 6; i++) {
                buffer[i] = 0xff;
            }
            // Data: 16 repetitions of MAC address
            for (let i = 0; i < 16; i++) {
                for (let j = 0; j < 6; j++) {
                    buffer[6 + i * 6 + j] = parseInt(macClean.substring(j * 2, j * 2 + 2), 16);
                }
            }

            return new Promise((resolve) => {
                const socket = dgram.createSocket("udp4");
                socket.send(buffer, 0, buffer.length, 9, "255.255.255.255", (err) => {
                    socket.close();
                    if (err) {
                        resolve({ content: [{ type: "text", text: `Failed to send WoL: ${err.message}` }], isError: true });
                    } else {
                        resolve({ content: [{ type: "text", text: `Magic packet sent to ${mac}` }] });
                    }
                });
            });
        }
    );
}
