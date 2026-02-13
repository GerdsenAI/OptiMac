/**
 * Network utility functions shared across tools.
 * Consolidates port checking and HTTP requests.
 */

import { createConnection } from "node:net";
import { runCommand } from "./shell.js";

/**
 * Check if a TCP port is accepting connections.
 * Returns true if a connection is established within the timeout.
 */
export async function checkPort(port: number, host = "127.0.0.1", timeout = 2000): Promise<boolean> {
    return new Promise((resolve) => {
        const socket = createConnection({ port, host, timeout });
        socket.on("connect", () => {
            socket.destroy();
            resolve(true);
        });
        socket.on("error", () => resolve(false));
        socket.on("timeout", () => {
            socket.destroy();
            resolve(false);
        });
    });
}

/**
 * HTTP GET request via curl. Returns status code and body.
 * Uses curl rather than node http to avoid event loop blocking with large responses.
 */
export async function httpGet(url: string, timeout = 5000): Promise<{ status: number; body: string }> {
    const result = await runCommand(
        "curl",
        ["-s", "-o", "-", "-w", "%{http_code}", "--max-time", String(timeout / 1000), url],
    );
    const body = result.stdout;
    const statusCode = parseInt(body.slice(-3), 10);
    return { status: isNaN(statusCode) ? 0 : statusCode, body: body.slice(0, -3) };
}

/**
 * Wait for a port to become available, with retries.
 * Returns true if the port is up within the retry window.
 */
export async function waitForPort(
    port: number,
    host = "127.0.0.1",
    retries = 10,
    intervalMs = 1000
): Promise<boolean> {
    for (let i = 0; i < retries; i++) {
        if (await checkPort(port, host)) return true;
        await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
}
