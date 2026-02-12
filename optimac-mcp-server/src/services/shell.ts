/**
 * Shell execution service with safety guards and timeout handling.
 * All system commands flow through here for centralized error handling.
 */

import { execFile, exec } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

const DEFAULT_TIMEOUT = 15_000; // 15s for most commands
const LONG_TIMEOUT = 60_000;   // 60s for heavy operations

export interface ShellResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/**
 * Execute a command safely with timeout and error capture.
 * Uses execFile (no shell injection) when possible.
 */
export async function runCommand(
  command: string,
  args: string[] = [],
  options: { timeout?: number; sudo?: boolean; shell?: boolean } = {}
): Promise<ShellResult> {
  const timeout = options.timeout ?? DEFAULT_TIMEOUT;

  try {
    if (options.sudo) {
      // sudo requires shell execution
      const fullCmd = `sudo ${command} ${args.join(" ")}`;
      const { stdout, stderr } = await execAsync(fullCmd, {
        timeout,
        env: { ...process.env, PATH: "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
      });
      return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
    }

    if (options.shell) {
      const fullCmd = `${command} ${args.join(" ")}`;
      const { stdout, stderr } = await execAsync(fullCmd, {
        timeout,
        env: { ...process.env, PATH: "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
      });
      return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
    }

    const { stdout, stderr } = await execFileAsync(command, args, {
      timeout,
      env: { ...process.env, PATH: "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
    });
    return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
  } catch (error: unknown) {
    const err = error as { stdout?: string; stderr?: string; code?: number | string; killed?: boolean };
    if (err.killed) {
      return {
        stdout: err.stdout?.trim() ?? "",
        stderr: `Command timed out after ${timeout}ms`,
        exitCode: 124,
      };
    }
    return {
      stdout: err.stdout?.trim() ?? "",
      stderr: err.stderr?.trim() ?? (error instanceof Error ? error.message : String(error)),
      exitCode: typeof err.code === "number" ? err.code : 1,
    };
  }
}

/**
 * Run an osascript (AppleScript) command.
 */
export async function runAppleScript(script: string, timeout = DEFAULT_TIMEOUT): Promise<string> {
  const result = await runCommand("osascript", ["-e", script], { timeout });
  if (result.exitCode !== 0) {
    throw new Error(`AppleScript failed: ${result.stderr}`);
  }
  return result.stdout;
}

/**
 * Run a JXA (JavaScript for Automation) command.
 */
export async function runJXA(script: string, timeout = DEFAULT_TIMEOUT): Promise<string> {
  const result = await runCommand("osascript", ["-l", "JavaScript", "-e", script], { timeout });
  if (result.exitCode !== 0) {
    throw new Error(`JXA failed: ${result.stderr}`);
  }
  return result.stdout;
}

export { DEFAULT_TIMEOUT, LONG_TIMEOUT };
