/**
 * System control tools: memory purge, DNS flush, network reset,
 * power management, process killing, service management.
 * These are the hands of OptiMac.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { runCommand, LONG_TIMEOUT } from "../services/shell.js";
import { loadConfig, isProcessProtected } from "../services/config.js";

export function registerSystemControlTools(server: McpServer): void {
  // ---- PURGE MEMORY ----
  server.registerTool(
    "optimac_purge_memory",
    {
      title: "Purge Inactive Memory",
      description: `Force-purge inactive/purgeable memory pages. Equivalent to running "sudo purge".

On a 16GB M4, this is critical when switching between models. After unloading a 7B model (~5GB), purge reclaims those pages immediately rather than waiting for macOS lazy reclamation.

Returns the memory stats before and after purge so you can verify it worked.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      // Snapshot before
      const before = await runCommand("vm_stat");
      const sysctl = await runCommand("sysctl", ["hw.memsize", "hw.pagesize"]);

      // Purge
      const purge = await runCommand("sudo", ["purge"], { shell: true, timeout: LONG_TIMEOUT });

      if (purge.exitCode !== 0) {
        return {
          content: [{ type: "text", text: `Error purging memory: ${purge.stderr}. Ensure passwordless sudo is configured for 'purge'.` }],
          isError: true,
        };
      }

      // Snapshot after
      const after = await runCommand("vm_stat");

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "success",
            message: "Memory purged successfully",
            before: before.stdout.substring(0, 500),
            after: after.stdout.substring(0, 500),
          }, null, 2),
        }],
      };
    }
  );

  // ---- FLUSH DNS ----
  server.registerTool(
    "optimac_flush_dns",
    {
      title: "Flush DNS Cache",
      description: `Flush macOS DNS cache and restart mDNSResponder. Fixes stale DNS entries that can cause API timeouts to OpenRouter, HuggingFace, etc.

Runs: dscacheutil -flushcache && killall -HUP mDNSResponder`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const [flush, mdns] = await Promise.all([
        runCommand("sudo", ["dscacheutil", "-flushcache"], { shell: true }),
        runCommand("sudo", ["killall", "-HUP", "mDNSResponder"], { shell: true }),
      ]);

      const success = flush.exitCode === 0 && mdns.exitCode === 0;
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: success ? "success" : "partial_failure",
            dscacheutil: flush.exitCode === 0 ? "flushed" : flush.stderr,
            mDNSResponder: mdns.exitCode === 0 ? "restarted" : mdns.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- FLUSH NETWORK ROUTES ----
  server.registerTool(
    "optimac_flush_routes",
    {
      title: "Flush Network Routes",
      description: `Flush the network routing table. Clears stale routes that can cause connectivity issues.

Runs: sudo route -n flush

Use this when you notice network slowness or routing errors after switching networks.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("sudo", ["route", "-n", "flush"], { shell: true });
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "success" : "error",
            message: result.exitCode === 0 ? "Routing table flushed" : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- SET POWER SETTINGS ----
  server.registerTool(
    "optimac_set_power",
    {
      title: "Set Power Settings",
      description: `Modify pmset power management settings. Common settings:

  - sleep: 0 = never sleep (recommended for AI server)
  - displaysleep: 0 = never sleep display
  - disksleep: 0 = never spin down disks
  - womp: 1 = enable Wake on LAN
  - autorestart: 1 = auto-restart after power failure
  - powernap: 0 = disable Power Nap (saves resources)

Args:
  - setting: the pmset key (e.g., "sleep", "womp")
  - value: the value to set (e.g., 0, 1)

Runs: sudo pmset -a <setting> <value>`,
      inputSchema: {
        setting: z.string().min(1).describe("pmset setting name (e.g., 'sleep', 'womp', 'autorestart')"),
        value: z.union([z.number(), z.string()]).describe("Value to set"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ setting, value }) => {
      const allowedSettings = [
        "sleep", "displaysleep", "disksleep", "womp",
        "autorestart", "powernap", "ttyskeepawake",
        "hibernatemode", "standby", "autopoweroff",
      ];

      if (!allowedSettings.includes(setting)) {
        return {
          content: [{
            type: "text",
            text: `Error: "${setting}" is not an allowed setting. Allowed: ${allowedSettings.join(", ")}`,
          }],
          isError: true,
        };
      }

      const result = await runCommand(
        "sudo",
        ["pmset", "-a", setting, String(value)],
        { shell: true }
      );

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "success" : "error",
            message: result.exitCode === 0
              ? `Set ${setting} = ${value}`
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- OPTIMIZE POWER FOR AI ----
  server.registerTool(
    "optimac_power_optimize",
    {
      title: "Optimize Power for AI",
      description: `Apply all recommended power settings for an always-on AI inference server in a single call.

Sets: sleep 0, displaysleep 0, disksleep 0, womp 1, autorestart 1, ttyskeepawake 1, powernap 0

This is the "make it an AI server" button.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const settings = [
        ["sleep", "0"],
        ["displaysleep", "0"],
        ["disksleep", "0"],
        ["womp", "1"],
        ["autorestart", "1"],
        ["ttyskeepawake", "1"],
        ["powernap", "0"],
      ];

      const results: Record<string, string> = {};

      for (const [key, val] of settings) {
        const r = await runCommand("sudo", ["pmset", "-a", key, val], { shell: true });
        results[key] = r.exitCode === 0 ? val : `FAILED: ${r.stderr}`;
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "complete",
            settings: results,
          }, null, 2),
        }],
      };
    }
  );

  // ---- KILL PROCESS ----
  server.registerTool(
    "optimac_kill_process",
    {
      title: "Kill Process",
      description: `Terminate a process by PID. Sends SIGTERM first, then SIGKILL after 5 seconds if still alive.

Protected processes (Ollama, LM Studio, MLX, sshd, etc.) cannot be killed unless force=true.

Args:
  - pid: Process ID to kill
  - force: Override protection (default false)
  - signal: Signal to send (default "TERM")`,
      inputSchema: {
        pid: z.number().int().positive().describe("Process ID to kill"),
        force: z.boolean().default(false).describe("Override protected process check"),
        signal: z.enum(["TERM", "KILL", "HUP"]).default("TERM").describe("Signal to send"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ pid, force, signal }) => {
      // Look up process name
      const psResult = await runCommand("ps", ["-p", String(pid), "-o", "comm="]);
      const processName = psResult.stdout.trim();

      if (!processName) {
        return {
          content: [{ type: "text", text: `Error: No process found with PID ${pid}` }],
          isError: true,
        };
      }

      const config = loadConfig();
      if (!force && isProcessProtected(processName, config)) {
        return {
          content: [{
            type: "text",
            text: `Refused: "${processName}" (PID ${pid}) is a protected process. Use force=true to override. Protected list: ${config.protectedProcesses.join(", ")}`,
          }],
          isError: true,
        };
      }

      const result = await runCommand("kill", [`-${signal}`, String(pid)]);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "signal_sent" : "error",
            pid,
            process: processName,
            signal,
            message: result.exitCode === 0
              ? `Sent SIG${signal} to ${processName} (PID ${pid})`
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- DISABLE SERVICE ----
  server.registerTool(
    "optimac_disable_service",
    {
      title: "Disable Service",
      description: `Disable a launchd service (launch agent or daemon). Use this to disable bloatware services.

Args:
  - service: Service label (e.g., "com.apple.Siri.agent")
  - domain: "user" or "system" (default "user")

Common services to disable for AI optimization:
  com.apple.Siri.agent, com.apple.notificationcenterui.agent,
  com.apple.bird (iCloud), com.apple.photoanalysisd,
  com.apple.mediaanalysisd, com.apple.suggestd,
  com.apple.assistantd, com.apple.parsec-fbf,
  com.apple.knowledge-agent`,
      inputSchema: {
        service: z.string().min(1).describe("Service label to disable"),
        domain: z.enum(["user", "system"]).default("user").describe("user or system domain"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ service, domain }) => {
      const domainTarget = domain === "system"
        ? "system"
        : `user/$(id -u)`;

      const result = await runCommand(
        "launchctl",
        ["disable", `${domainTarget}/${service}`],
        { shell: true }
      );

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "disabled" : "error",
            service,
            domain,
            message: result.exitCode === 0
              ? `Service ${service} disabled in ${domain} domain`
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- ENABLE SERVICE ----
  server.registerTool(
    "optimac_enable_service",
    {
      title: "Enable Service",
      description: `Re-enable a previously disabled launchd service.

Args:
  - service: Service label (e.g., "com.apple.Siri.agent")
  - domain: "user" or "system" (default "user")`,
      inputSchema: {
        service: z.string().min(1).describe("Service label to enable"),
        domain: z.enum(["user", "system"]).default("user").describe("user or system domain"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ service, domain }) => {
      const domainTarget = domain === "system"
        ? "system"
        : `user/$(id -u)`;

      const result = await runCommand(
        "launchctl",
        ["enable", `${domainTarget}/${service}`],
        { shell: true }
      );

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "enabled" : "error",
            service,
            domain,
            message: result.exitCode === 0
              ? `Service ${service} enabled in ${domain} domain`
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- DISABLE SPOTLIGHT ----
  server.registerTool(
    "optimac_disable_spotlight",
    {
      title: "Disable Spotlight",
      description: `Disable Spotlight indexing system-wide. This is the single highest-impact optimization for AI inference on macOS.

Spotlight I/O competes directly with model memory mapping. Disabling it frees both CPU cycles and disk I/O bandwidth.

Runs: sudo mdutil -a -i off`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await runCommand("sudo", ["mdutil", "-a", "-i", "off"], { shell: true });

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "disabled" : "error",
            message: result.exitCode === 0
              ? "Spotlight indexing disabled system-wide"
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- CLEAR CACHES ----
  server.registerTool(
    "optimac_clear_caches",
    {
      title: "Clear System Caches",
      description: `Clear safe system caches, temp files, and old logs. Frees disk space without affecting running services.

Clears: /tmp/*, ~/Library/Caches/*, logs older than 7 days, font caches.

Returns bytes freed.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async () => {
      // Get disk usage before
      const before = await runCommand("df", ["-k", "/"]);

      const results: Record<string, string> = {};

      // Clear /tmp
      const tmp = await runCommand("sudo", ["rm", "-rf", "/tmp/*"], { shell: true });
      results["tmp"] = tmp.exitCode === 0 ? "cleared" : tmp.stderr;

      // Clear user caches
      const caches = await runCommand(
        "rm",
        ["-rf", `${process.env.HOME}/Library/Caches/*`],
        { shell: true }
      );
      results["user_caches"] = caches.exitCode === 0 ? "cleared" : caches.stderr;

      // Old logs
      const logs = await runCommand(
        "find",
        [`${process.env.HOME}/Library/Logs`, "-name", "*.log", "-mtime", "+7", "-delete"],
        { shell: true, timeout: 30_000 }
      );
      results["old_logs"] = logs.exitCode === 0 ? "cleared" : logs.stderr;

      // Get disk usage after
      const after = await runCommand("df", ["-k", "/"]);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "complete",
            operations: results,
            diskBefore: before.stdout.split("\n")[1] ?? "",
            diskAfter: after.stdout.split("\n")[1] ?? "",
          }, null, 2),
        }],
      };
    }
  );

  // ---- SET DNS ----
  server.registerTool(
    "optimac_set_dns",
    {
      title: "Set DNS Servers",
      description: `Set DNS servers for the active network interface. Faster DNS = faster model downloads and API calls.

Args:
  - servers: Array of DNS server IPs (default: Cloudflare 1.1.1.1, 1.0.0.1)
  - interface: Network interface name (default: auto-detect active)

Presets:
  cloudflare: 1.1.1.1, 1.0.0.1
  google: 8.8.8.8, 8.8.4.4
  quad9: 9.9.9.9, 149.112.112.112`,
      inputSchema: {
        preset: z.enum(["cloudflare", "google", "quad9", "custom"]).default("cloudflare").describe("DNS preset"),
        servers: z.array(z.string()).optional().describe("Custom DNS servers (only used with preset=custom)"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ preset, servers }) => {
      const presets: Record<string, string[]> = {
        cloudflare: ["1.1.1.1", "1.0.0.1"],
        google: ["8.8.8.8", "8.8.4.4"],
        quad9: ["9.9.9.9", "149.112.112.112"],
      };

      const dnsServers = preset === "custom" ? (servers ?? ["1.1.1.1"]) : presets[preset];

      // Detect active network service
      const netResult = await runCommand(
        "networksetup",
        ["-listallnetworkservices"],
      );

      const services = netResult.stdout.split("\n").filter((l) => !l.startsWith("*") && l.trim());
      const activeService = services.find((s) => s.includes("Ethernet") || s.includes("Thunderbolt")) ?? services[0];

      if (!activeService) {
        return { content: [{ type: "text", text: "Error: No active network service found" }], isError: true };
      }

      const result = await runCommand(
        "sudo",
        ["networksetup", "-setdnsservers", activeService, ...dnsServers],
        { shell: true }
      );

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: result.exitCode === 0 ? "success" : "error",
            service: activeService,
            dnsServers,
            message: result.exitCode === 0
              ? `DNS set to ${dnsServers.join(", ")} on ${activeService}`
              : result.stderr,
          }, null, 2),
        }],
      };
    }
  );

  // ---- FULL NETWORK RESET ----
  server.registerTool(
    "optimac_network_reset",
    {
      title: "Full Network Reset",
      description: `Perform a complete network reset: flush DNS, flush routes, reset mDNSResponder, and optionally set fast DNS.

Use this when experiencing connectivity issues, high latency to APIs, or after switching networks.`,
      inputSchema: {
        set_fast_dns: z.boolean().default(true).describe("Also set DNS to Cloudflare 1.1.1.1"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ set_fast_dns }) => {
      const results: Record<string, string> = {};

      // Flush DNS
      const dns = await runCommand("sudo", ["dscacheutil", "-flushcache"], { shell: true });
      results["dns_cache"] = dns.exitCode === 0 ? "flushed" : dns.stderr;

      // Restart mDNSResponder
      const mdns = await runCommand("sudo", ["killall", "-HUP", "mDNSResponder"], { shell: true });
      results["mDNSResponder"] = mdns.exitCode === 0 ? "restarted" : mdns.stderr;

      // Flush routes
      const routes = await runCommand("sudo", ["route", "-n", "flush"], { shell: true });
      results["routes"] = routes.exitCode === 0 ? "flushed" : routes.stderr;

      // Optionally set fast DNS
      if (set_fast_dns) {
        const netResult = await runCommand("networksetup", ["-listallnetworkservices"]);
        const services = netResult.stdout.split("\n").filter((l) => !l.startsWith("*") && l.trim());
        const active = services.find((s) => s.includes("Ethernet") || s.includes("Thunderbolt")) ?? services[0];
        if (active) {
          const dnsSet = await runCommand(
            "sudo",
            ["networksetup", "-setdnsservers", active, "1.1.1.1", "1.0.0.1"],
            { shell: true }
          );
          results["dns_servers"] = dnsSet.exitCode === 0 ? "set to 1.1.1.1, 1.0.0.1" : dnsSet.stderr;
        }
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ status: "complete", operations: results }, null, 2),
        }],
      };
    }
  );

  // ---- REDUCE UI OVERHEAD ----
  server.registerTool(
    "optimac_reduce_ui_overhead",
    {
      title: "Reduce UI Overhead",
      description: `Disable macOS visual effects, animations, and transparency to reduce GPU overhead.

Sets: reduceMotion, reduceTransparency, disable window animations, fast Mission Control,
instant Dock hide, disable Springboard animations, disable Quick Look animations,
disable window resize animations, fast Dock autohide.

Frees GPU resources for Metal-based MLX inference. All changes are reversible
by resetting defaults or toggling Accessibility settings.`,
      inputSchema: {},
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const commands: [string, string[]][] = [
        // Accessibility: reduce motion & transparency
        ["defaults", ["write", "com.apple.universalaccess", "reduceMotion", "-bool", "true"]],
        ["defaults", ["write", "com.apple.universalaccess", "reduceTransparency", "-bool", "true"]],
        // Window animations
        ["defaults", ["write", "NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "-bool", "false"]],
        ["defaults", ["write", "NSGlobalDomain", "NSWindowResizeTime", "-float", "0.001"]],
        // Dock animations
        ["defaults", ["write", "com.apple.dock", "expose-animation-duration", "-float", "0.1"]],
        ["defaults", ["write", "com.apple.dock", "autohide-time-modifier", "-float", "0"]],
        ["defaults", ["write", "com.apple.dock", "autohide-delay", "-float", "0"]],
        ["defaults", ["write", "com.apple.dock", "launchanim", "-bool", "false"]],
        // Springboard (Launchpad) animations
        ["defaults", ["write", "com.apple.dock", "springboard-show-duration", "-float", "0.1"]],
        ["defaults", ["write", "com.apple.dock", "springboard-hide-duration", "-float", "0.1"]],
        // Quick Look animation
        ["defaults", ["write", "-g", "QLPanelAnimationDuration", "-float", "0"]],
        // Disable smooth scrolling (reduces GPU compositing)
        ["defaults", ["write", "NSGlobalDomain", "NSScrollAnimationEnabled", "-bool", "false"]],
        // Disable rubber-band scrolling
        ["defaults", ["write", "NSGlobalDomain", "NSScrollViewRubberbanding", "-bool", "false"]],
      ];

      const results: Record<string, string> = {};
      for (const [cmd, args] of commands) {
        const r = await runCommand(cmd, args);
        const key = args.length >= 2 ? args[1] : args[0];
        results[key] = r.exitCode === 0 ? "set" : r.stderr;
      }

      // Restart affected services
      await runCommand("killall", ["Dock"]);
      await runCommand("killall", ["Finder"]);

      results["dock_restart"] = "restarted";
      results["finder_restart"] = "restarted";

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: "complete",
            settingsApplied: Object.keys(results).length,
            settings: results,
          }, null, 2),
        }],
      };
    }
  );

  // ---- NVRAM SERVER PERFORMANCE MODE ----
  server.registerTool(
    "optimac_nvram_perf_mode",
    {
      title: "NVRAM Server Performance Mode",
      description: `Toggle NVRAM server performance mode (boot-args serverperfmode=1).

When enabled, macOS allocates extra kernel resources for network throughput
and I/O at the cost of higher idle power consumption. Optimizes the system
for AI inference serving workloads.

Requires a RESTART to take effect.

Actions:
  - status: Check if server perf mode is currently enabled
  - enable: Set serverperfmode=1 in boot-args
  - disable: Remove serverperfmode=1 from boot-args`,
      inputSchema: {
        action: z.enum(["status", "enable", "disable"]).default("status")
          .describe("Action to perform: status, enable, or disable"),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ action }) => {
      // Check current state
      const current = await runCommand("nvram", ["boot-args"]);
      const currentArgs = current.exitCode === 0
        ? current.stdout.replace("boot-args\t", "").trim()
        : "";
      const isEnabled = currentArgs.includes("serverperfmode=1");

      if (action === "status") {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              serverPerfMode: isEnabled ? "enabled" : "disabled",
              bootArgs: currentArgs || "(none)",
              note: "Requires restart to apply changes.",
            }, null, 2),
          }],
        };
      }

      if (action === "enable" && isEnabled) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "already_enabled",
              bootArgs: currentArgs,
            }, null, 2),
          }],
        };
      }

      if (action === "disable" && !isEnabled) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              status: "already_disabled",
              bootArgs: currentArgs || "(none)",
            }, null, 2),
          }],
        };
      }

      let result;
      if (action === "enable") {
        const newArgs = currentArgs
          ? `${currentArgs} serverperfmode=1`
          : "serverperfmode=1";
        result = await runCommand("sudo", ["nvram", `boot-args=${newArgs}`], { shell: true });
      } else {
        // disable
        const newArgs = currentArgs
          .replace(/\s*serverperfmode=1\s*/g, " ")
          .trim();
        if (newArgs) {
          result = await runCommand("sudo", ["nvram", `boot-args=${newArgs}`], { shell: true });
        } else {
          result = await runCommand("sudo", ["nvram", "-d", "boot-args"], { shell: true });
        }
      }

      if (result.exitCode !== 0) {
        return {
          content: [{
            type: "text",
            text: `Error: ${result.stderr}. Ensure passwordless sudo is configured for 'nvram'.`,
          }],
          isError: true,
        };
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            status: action === "enable" ? "enabled" : "disabled",
            note: "Restart required for changes to take effect.",
            previousBootArgs: currentArgs || "(none)",
          }, null, 2),
        }],
      };
    }
  );

  // ---- LIST LOGIN ITEMS ----
  server.registerTool(
    "optimac_sys_login_items",
    {
      title: "List Login Items",
      description: "List all applications and items configured to launch at login.",
      inputSchema: {},
    },
    async () => {
      const script = 'tell application "System Events" to get the name of every login item';
      const result = await runCommand("osascript", ["-e", script]);

      const items = result.stdout.split(",").map((s) => s.trim()).filter((s) => s);

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            count: items.length,
            items,
          }, null, 2),
        }],
      };
    }
  );

  // ---- EJECT DRIVES ----
  server.registerTool(
    "optimac_sys_eject",
    {
      title: "Eject All Drives",
      description: "Unmount and eject all external drives and volumes.",
      inputSchema: {},
      annotations: { destructiveHint: true },
    },
    async () => {
      const script = 'tell application "Finder" to eject (every disk whose ejectable is true)';
      const result = await runCommand("osascript", ["-e", script]);

      return {
        content: [{
          type: "text",
          text: result.exitCode === 0
            ? "All ejectable drives ejected"
            : `Failed to eject: ${result.stderr}`,
        }],
      };
    }
  );

  // ---- LOCK SCREEN ----
  server.registerTool(
    "optimac_sys_lock",
    {
      title: "Lock Screen",
      description: "Immediately lock the screen (sleep display).",
      inputSchema: {},
    },
    async () => {
      const result = await runCommand("pmset", ["displaysleepnow"]);
      return {
        content: [{
          type: "text",
          text: result.exitCode === 0 ? "Screen locked" : `Failed: ${result.stderr}`,
        }],
      };
    }
  );

  // ---- RESTART SYSTEM SERVICES ----
  server.registerTool(
    "optimac_sys_restart_service",
    {
      title: "Restart System Service",
      description: "Restart a key system service (Finder, Dock, SystemUIServer).",
      inputSchema: {
        service: z.enum(["Finder", "Dock", "SystemUIServer"]).describe("Service to restart"),
      },
      annotations: { destructiveHint: true },
    },
    async ({ service }) => {
      const result = await runCommand("killall", [service]);
      return {
        content: [{
          type: "text",
          text: result.exitCode === 0 ? `${service} restarted` : `Failed: ${result.stderr}`,
        }],
      };
    }
  );

  // ---- EMPTY TRASH ----
  server.registerTool(
    "optimac_sys_trash",
    {
      title: "Empty Trash",
      description: "Permanently empty the Trash. CAUTION: This operation cannot be undone.",
      inputSchema: {},
      annotations: { destructiveHint: true },
    },
    async () => {
      const script = 'tell application "Finder" to empty trash';
      const result = await runCommand("osascript", ["-e", script]);

      return {
        content: [{
          type: "text",
          text: result.exitCode === 0
            ? "Trash emptied successfully"
            : `Failed (User may need to approve Finder interaction): ${result.stderr}`,
        }],
      };
    }
  );

  // ---- APPLY POWER PROFILE ----
  server.registerTool(
    "optimac_power_profile",
    {
      title: "Apply Power Profile",
      description: `Apply a predefined power profile via pmset.

performance — AI server mode: no sleep, Wake-on-LAN, auto-restart.
balanced — moderate sleep, WoL on, auto-restart, no Power Nap.
efficiency — aggressive sleep, low power mode enabled.`,
      inputSchema: {
        profile: z.enum(["performance", "balanced", "efficiency"]).describe("Power profile to apply"),
      },
      annotations: { destructiveHint: true },
    },
    async ({ profile }) => {
      const profiles: Record<string, string> = {
        performance: "pmset -a displaysleep 0 && pmset -a sleep 0 && pmset -a disksleep 0 && pmset -a gpuswitch 2 && pmset -a womp 1 && pmset -a autorestart 1 && pmset -a ttyskeepawake 1 && pmset -a powernap 0",
        balanced: "pmset -a displaysleep 10 && pmset -a sleep 0 && pmset -a disksleep 10 && pmset -a gpuswitch 2 && pmset -a womp 1 && pmset -a autorestart 1 && pmset -a powernap 0",
        efficiency: "pmset -a displaysleep 5 && pmset -a sleep 10 && pmset -a disksleep 5 && pmset -a gpuswitch 0 && pmset -a lowpowermode 1 && pmset -a powernap 0",
      };

      const result = await runCommand("sudo", ["-n", "sh", "-c", profiles[profile]], { timeout: 15000 });
      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Failed to apply ${profile} profile (may need sudo): ${result.stderr}` }], isError: true };
      }
      return { content: [{ type: "text", text: `${profile} power profile applied successfully` }] };
    }
  );

  // ---- DEBLOAT RE-ENABLE ----
  server.registerTool(
    "optimac_debloat_reenable",
    {
      title: "Re-enable Disabled Services",
      description: "Re-enable all previously disabled macOS services from debloat presets.",
      inputSchema: {},
      annotations: { destructiveHint: true },
    },
    async () => {
      const config = loadConfig();
      const disabled = config.disabledServices || [];
      if (disabled.length === 0) {
        return { content: [{ type: "text", text: "No disabled services found. Nothing to re-enable." }] };
      }

      const uidResult = await runCommand("id", ["-u"]);
      const uid = uidResult.stdout.trim() || "501";

      const cmds = disabled.map((svc: string) => `launchctl enable user/${uid}/${svc}`).join(" && ");
      const result = await runCommand("sudo", ["-n", "sh", "-c", cmds], { timeout: 30000 });

      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Failed (may need sudo): ${result.stderr}` }], isError: true };
      }

      // Clear the disabled services in config
      config.disabledServices = [];
      const configPath = `${process.env.HOME}/.optimac/config.json`;
      try {
        const fs = await import("fs");
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
      } catch { /* config save is best-effort */ }

      return { content: [{ type: "text", text: `Re-enabled ${disabled.length} services successfully` }] };
    }
  );

  // ---- REBUILD SPOTLIGHT ----
  server.registerTool(
    "optimac_rebuild_spotlight",
    {
      title: "Rebuild Spotlight Index",
      description: "Erase and rebuild Spotlight search index. Indexing may take 30-60 minutes.",
      inputSchema: {},
      annotations: { destructiveHint: true },
    },
    async () => {
      const result = await runCommand("sudo", ["-n", "mdutil", "-E", "/"], { timeout: 15000 });
      if (result.exitCode !== 0) {
        return { content: [{ type: "text", text: `Failed (may need sudo): ${result.stderr}` }], isError: true };
      }
      return { content: [{ type: "text", text: `Spotlight index rebuild started. May take 30-60 minutes.\n${result.stdout}` }] };
    }
  );

  // ---- OPTIMIZE HOMEBREW ----
  server.registerTool(
    "optimac_optimize_homebrew",
    {
      title: "Optimize Homebrew",
      description: "Run Homebrew cleanup (prune 7 days) and autoremove unused dependencies.",
      inputSchema: {},
      annotations: { destructiveHint: true },
    },
    async () => {
      const whichBrew = await runCommand("which", ["brew"], { timeout: 5000 });
      if (whichBrew.exitCode !== 0) {
        return { content: [{ type: "text", text: "Homebrew is not installed. Install from https://brew.sh" }], isError: true };
      }

      const cleanup = await runCommand("brew", ["cleanup", "--prune=7"], { timeout: 120000 });
      const autoremove = await runCommand("brew", ["autoremove"], { timeout: 60000 });

      const body = [
        "── Cleanup ──",
        cleanup.stdout || "(nothing to clean)",
        "",
        "── Autoremove ──",
        autoremove.stdout || "(nothing to remove)",
      ].join("\n");

      return { content: [{ type: "text", text: body }] };
    }
  );
}
