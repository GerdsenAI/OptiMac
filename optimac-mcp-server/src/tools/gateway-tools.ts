/**
 * Moltbot Gateway management tools.
 * Start, stop, monitor, and configure the GerdsenAI Moltbot-Local gateway.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { existsSync } from "node:fs";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { loadConfig } from "../services/config.js";
import { checkPort, waitForPort } from "../services/net.js";

/** Resolve the moltbot CLI binary — global install or pnpm in repo */
async function resolveMoltbot(repoPath: string): Promise<{ cmd: string; args: string[]; cwd?: string }> {
  const which = await runCommand("which", ["moltbot"]);
  if (which.exitCode === 0 && which.stdout.trim()) {
    return { cmd: which.stdout.trim(), args: [] };
  }
  // Fall back to pnpm moltbot in repo directory
  return { cmd: "pnpm", args: ["moltbot"], cwd: repoPath };
}

/** Run a moltbot CLI command and return the output */
async function runMoltbot(
  subcommand: string[],
  opts: { timeout?: number } = {}
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const config = loadConfig();
  const repoPath = config.gatewayRepoPath;

  if (!existsSync(repoPath)) {
    return {
      stdout: "",
      stderr: `Gateway repo not found at ${repoPath}. Set gatewayRepoPath in ~/.optimac/config.json`,
      exitCode: 1,
    };
  }

  const bin = await resolveMoltbot(repoPath);
  const fullArgs = [...bin.args, ...subcommand];
  // Prepend common Node/pnpm/Homebrew locations so runCommand's PATH includes them
  const extraPath = `${process.env.HOME}/Library/pnpm:${process.env.HOME}/.local/bin:/opt/homebrew/bin`;
  const origPath = process.env.PATH ?? "";
  process.env.PATH = `${extraPath}:${origPath}`;

  try {
    return await runCommand(bin.cmd, fullArgs, {
      timeout: opts.timeout ?? LONG_TIMEOUT,
      cwd: bin.cwd ?? repoPath,
      shell: true,
    });
  } finally {
    process.env.PATH = origPath;
  }
}

export function registerGatewayTools(server: McpServer): void {
  // ---- GATEWAY STATUS ----
  server.registerTool(
    "optimac_gateway_status",
    {
      title: "Gateway Status",
      description: `Check Moltbot-Local gateway health: whether it's running, port status, and basic info.

Returns:
  - running: whether port 18789 is accepting connections
  - port: configured gateway port
  - repoPath: path to the gateway repo
  - launchd: whether the launchd service is registered
  - moltbotStatus: output from 'moltbot status' (if running)`,
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
      const port = config.gatewayPort;
      const repoPath = config.gatewayRepoPath;
      const portUp = await checkPort(port);

      const result: Record<string, unknown> = {
        running: portUp,
        port,
        repoPath,
        repoExists: existsSync(repoPath),
      };

      // Check launchd service
      const launchctl = await runCommand("launchctl", ["list"], { shell: true });
      const hasService = launchctl.stdout.includes("bot.molt.gateway");
      result["launchdService"] = hasService;

      // If running, get moltbot status
      if (portUp) {
        const status = await runMoltbot(["status"]);
        result["moltbotStatus"] = status.exitCode === 0 ? status.stdout : status.stderr;
      }

      // Get gateway process info
      const ps = await runCommand("ps", ["aux"], { shell: true });
      const gatewayLine = ps.stdout.split("\n").find((l) => l.includes("moltbot") && l.includes("gateway"));
      if (gatewayLine) {
        const parts = gatewayLine.trim().split(/\s+/);
        result["pid"] = parseInt(parts[1] ?? "0", 10);
        result["rssMB"] = Math.round(parseInt(parts[5] ?? "0", 10) / 1024);
      }

      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  // ---- GATEWAY DOCTOR ----
  server.registerTool(
    "optimac_gateway_doctor",
    {
      title: "Gateway Doctor",
      description: `Run Moltbot diagnostics to surface misconfigurations, missing credentials,
and legacy issues. Equivalent to 'moltbot doctor'.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runMoltbot(["doctor"]);
      return {
        content: [{ type: "text", text: JSON.stringify({
          exitCode: result.exitCode,
          output: result.stdout || result.stderr,
        }, null, 2) }],
        ...(result.exitCode !== 0 ? { isError: true } : {}),
      };
    }
  );

  // ---- GATEWAY LOGS ----
  server.registerTool(
    "optimac_gateway_logs",
    {
      title: "Gateway Logs",
      description: `Read recent Moltbot gateway log lines from the log file.
Default: last 50 lines. Useful for debugging gateway issues.`,
      inputSchema: {
        lines: z.number().int().min(1).max(500).default(50)
          .describe("Number of log lines to return (default 50, max 500)"),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ lines }) => {
      const logPaths = [
        "/tmp/moltbot/moltbot-gateway.log",
        "/tmp/moltbot-gateway.log",
      ];

      let logPath: string | null = null;
      for (const p of logPaths) {
        if (existsSync(p)) { logPath = p; break; }
      }

      if (!logPath) {
        return {
          content: [{ type: "text", text: JSON.stringify({
            error: "No gateway log file found",
            searched: logPaths,
          }, null, 2) }],
          isError: true,
        };
      }

      const result = await runCommand("tail", ["-n", String(lines), logPath]);
      return {
        content: [{ type: "text", text: JSON.stringify({
          logFile: logPath,
          lines: result.stdout.split("\n").length,
          content: result.stdout,
        }, null, 2) }],
      };
    }
  );

  // ---- GATEWAY CHANNELS ----
  server.registerTool(
    "optimac_gateway_channels",
    {
      title: "Gateway Channels",
      description: `Check MS Teams channel connection status. Probes the channel to verify
it's connected and responding. Equivalent to 'moltbot channels status --probe'.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async () => {
      const result = await runMoltbot(["channels", "status", "--probe"]);
      return {
        content: [{ type: "text", text: JSON.stringify({
          exitCode: result.exitCode,
          output: result.stdout || result.stderr,
        }, null, 2) }],
        ...(result.exitCode !== 0 ? { isError: true } : {}),
      };
    }
  );

  // ---- GATEWAY LOCAL AI ----
  server.registerTool(
    "optimac_gateway_local_ai",
    {
      title: "Gateway Local AI Discovery",
      description: `Discover local AI endpoints visible to the gateway (Ollama, LM Studio, vLlama).
Equivalent to 'moltbot local-ai discover'.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async () => {
      const result = await runMoltbot(["local-ai", "discover"]);
      return {
        content: [{ type: "text", text: JSON.stringify({
          exitCode: result.exitCode,
          output: result.stdout || result.stderr,
        }, null, 2) }],
        ...(result.exitCode !== 0 ? { isError: true } : {}),
      };
    }
  );

  // ---- GATEWAY RESTART ----
  server.registerTool(
    "optimac_gateway_restart",
    {
      title: "Gateway Restart",
      description: `Restart the Moltbot gateway launchd daemon. Uses launchctl kickstart
to restart the bot.molt.gateway service. Falls back to process kill + re-launch if
launchd service isn't registered.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const config = loadConfig();
      const uid = process.getuid?.() ?? 501;

      // Try launchctl kickstart first
      const kickstart = await runCommand(
        "launchctl",
        ["kickstart", "-k", `gui/${uid}/bot.molt.gateway`],
        { shell: true }
      );

      if (kickstart.exitCode === 0) {
        // Wait for port to come up (retry for up to 10s)
        const portUp = await waitForPort(config.gatewayPort, "127.0.0.1", 10, 1000);
        return {
          content: [{ type: "text", text: JSON.stringify({
            method: "launchctl kickstart",
            success: true,
            portUp,
            port: config.gatewayPort,
          }, null, 2) }],
        };
      }

      // Fallback: kill and re-launch via nohup
      // Pattern matches both "moltbot-gateway" and "moltbot gateway"
      await runCommand("pkill", ["-f", "moltbot.*gateway"], { shell: true });
      // Small delay for process to die
      await new Promise((r) => setTimeout(r, 1500));

      const repoPath = config.gatewayRepoPath;
      const port = String(config.gatewayPort);
      // Launch in background with nohup so it survives after this command returns
      await runCommand(
        "nohup",
        ["pnpm", "moltbot", "gateway", "run", "--bind", "loopback", "--port", port, "--force"],
        { cwd: repoPath, shell: true, timeout: 5_000 }
      );

      // Wait for port to come up
      const portUp = await waitForPort(config.gatewayPort, "127.0.0.1", 10, 1000);

      return {
        content: [{ type: "text", text: JSON.stringify({
          method: "fallback (pkill + nohup moltbot gateway run)",
          launchctlError: kickstart.stderr,
          portUp,
          port: config.gatewayPort,
        }, null, 2) }],
      };
    }
  );

  // ---- GATEWAY CONFIG ----
  server.registerTool(
    "optimac_gateway_config",
    {
      title: "Gateway Config",
      description: `Get or set a Moltbot configuration value. Uses 'moltbot config get/set'.

Common keys:
  - agent.model (e.g. "anthropic/claude-opus-4-6")
  - gateway.mode (e.g. "local")
  - agents.defaults.maxConcurrent
  - agents.defaults.subagents.maxConcurrent
  - tools.media.concurrency`,
      inputSchema: {
        action: z.enum(["get", "set"]).describe("Whether to get or set a config value"),
        key: z.string().describe("Config key (e.g. 'agent.model')"),
        value: z.string().optional().describe("Value to set (required for action=set)"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ action, key, value }) => {
      if (action === "set" && !value) {
        return {
          content: [{ type: "text", text: JSON.stringify({
            error: "value is required when action=set",
          }, null, 2) }],
          isError: true,
        };
      }

      const args = action === "get"
        ? ["config", "get", key]
        : ["config", "set", key, value!];

      const result = await runMoltbot(args);
      return {
        content: [{ type: "text", text: JSON.stringify({
          action,
          key,
          ...(action === "set" ? { value } : {}),
          exitCode: result.exitCode,
          output: result.stdout || result.stderr,
        }, null, 2) }],
        ...(result.exitCode !== 0 ? { isError: true } : {}),
      };
    }
  );

  // ---- GATEWAY UPDATE ----
  server.registerTool(
    "optimac_gateway_update",
    {
      title: "Gateway Update",
      description: `Pull latest code, rebuild, and restart the Moltbot gateway.
Runs: git pull --rebase origin main && pnpm install && pnpm build, then restarts the daemon.

This is a heavy operation (30-120s depending on changes).`,
      inputSchema: {
        restart: z.boolean().default(true)
          .describe("Restart the gateway after rebuilding (default true)"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async ({ restart }) => {
      const config = loadConfig();
      const repoPath = config.gatewayRepoPath;

      if (!existsSync(repoPath)) {
        return {
          content: [{ type: "text", text: JSON.stringify({
            error: `Gateway repo not found at ${repoPath}`,
          }, null, 2) }],
          isError: true,
        };
      }

      const steps: Record<string, unknown>[] = [];

      // Step 1: git pull
      const pull = await runCommand("git", ["pull", "--rebase", "origin", "main"], {
        cwd: repoPath,
        timeout: LONG_TIMEOUT,
        shell: true,
      });
      steps.push({ step: "git pull", exitCode: pull.exitCode, output: pull.stdout || pull.stderr });

      if (pull.exitCode !== 0) {
        return {
          content: [{ type: "text", text: JSON.stringify({ steps, error: "git pull failed" }, null, 2) }],
          isError: true,
        };
      }

      // Step 2: pnpm install
      const install = await runCommand("pnpm", ["install"], {
        cwd: repoPath,
        timeout: LONG_TIMEOUT * 2,
        shell: true,
      });
      steps.push({ step: "pnpm install", exitCode: install.exitCode, output: install.stdout.slice(-500) || install.stderr });

      if (install.exitCode !== 0) {
        return {
          content: [{ type: "text", text: JSON.stringify({ steps, error: "pnpm install failed" }, null, 2) }],
          isError: true,
        };
      }

      // Step 3: pnpm build
      const build = await runCommand("pnpm", ["build"], {
        cwd: repoPath,
        timeout: LONG_TIMEOUT * 2,
        shell: true,
      });
      steps.push({ step: "pnpm build", exitCode: build.exitCode, output: build.stdout.slice(-500) || build.stderr });

      if (build.exitCode !== 0) {
        return {
          content: [{ type: "text", text: JSON.stringify({ steps, error: "pnpm build failed" }, null, 2) }],
          isError: true,
        };
      }

      // Step 4: Restart (optional)
      if (restart) {
        const uid = process.getuid?.() ?? 501;
        const kick = await runCommand("launchctl", ["kickstart", "-k", `gui/${uid}/bot.molt.gateway`], { shell: true });
        steps.push({ step: "restart", method: "launchctl kickstart", exitCode: kick.exitCode });
      }

      return {
        content: [{ type: "text", text: JSON.stringify({ success: true, steps }, null, 2) }],
      };
    }
  );
}
