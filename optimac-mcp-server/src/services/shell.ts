/**
 * Shell execution service with safety guards, timeout handling, and error classification.
 * All system commands flow through here for centralized error handling.
 */

import { execFile, exec } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

const DEFAULT_TIMEOUT = 15_000; // 15s for most commands
const LONG_TIMEOUT = 60_000;   // 60s for heavy operations

export type ErrorType = "TIMEOUT" | "NOT_FOUND" | "PERMISSION_DENIED" | "SIGNAL" | "GENERIC";

export interface ShellResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  errorType?: ErrorType;
}

/** Classify error based on error object properties and stderr content */
function classifyError(
  err: { code?: number | string; killed?: boolean; signal?: string; stderr?: string },
  stderr: string
): ErrorType {
  if (err.killed || err.signal === "SIGTERM") return "TIMEOUT";
  if (err.code === "ENOENT" || stderr.includes("command not found") || stderr.includes("No such file")) return "NOT_FOUND";
  if (stderr.includes("Permission denied") || stderr.includes("Operation not permitted") || err.code === "EACCES") return "PERMISSION_DENIED";
  if (err.signal) return "SIGNAL";
  return "GENERIC";
}

/**
 * Execute a command safely with timeout and error capture.
 * Uses execFile (no shell injection) when possible.
 * Classifies errors for smarter handling in tool code.
 */
export async function runCommand(
  command: string,
  args: string[] = [],
  options: { timeout?: number; sudo?: boolean; shell?: boolean; cwd?: string } = {}
): Promise<ShellResult> {
  const timeout = options.timeout ?? DEFAULT_TIMEOUT;
  const execOpts = {
    timeout,
    env: { ...process.env, PATH: "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
    ...(options.cwd ? { cwd: options.cwd } : {}),
  };

  try {
    if (options.sudo) {
      // sudo requires shell execution
      const fullCmd = `sudo ${command} ${args.join(" ")}`;
      const { stdout, stderr } = await execAsync(fullCmd, execOpts);
      return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
    }

    if (options.shell) {
      const fullCmd = `${command} ${args.join(" ")}`;
      const { stdout, stderr } = await execAsync(fullCmd, execOpts);
      return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
    }

    const { stdout, stderr } = await execFileAsync(command, args, execOpts);
    return { stdout: stdout.trim(), stderr: stderr.trim(), exitCode: 0 };
  } catch (error: unknown) {
    const err = error as { stdout?: string; stderr?: string; code?: number | string; killed?: boolean; signal?: string };
    const stderr = err.stderr?.trim() ?? (error instanceof Error ? error.message : String(error));
    const errorType = classifyError(err, stderr);

    if (errorType === "TIMEOUT") {
      return {
        stdout: err.stdout?.trim() ?? "",
        stderr: `Command timed out after ${timeout}ms`,
        exitCode: 124,
        errorType,
      };
    }

    return {
      stdout: err.stdout?.trim() ?? "",
      stderr,
      exitCode: typeof err.code === "number" ? err.code : 1,
      errorType,
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
