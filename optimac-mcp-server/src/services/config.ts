/**
 * OptiMac configuration management.
 * Reads/writes config from ~/.optimac/config.json
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const CONFIG_DIR = join(homedir(), ".optimac");
const CONFIG_FILE = join(CONFIG_DIR, "config.json");

export interface OptiMacConfig {
  /** Processes that should never be auto-killed */
  protectedProcesses: string[];

  /** Memory pressure thresholds (0.0-1.0) */
  memoryWarningThreshold: number;
  memoryCriticalThreshold: number;

  /** Whether to auto-kill non-protected processes at critical pressure */
  autoKillAtCritical: boolean;

  /** Max RSS in MB for a non-protected process before it's flagged */
  maxProcessRSSMB: number;

  /** Maintenance interval in seconds */
  maintenanceIntervalSec: number;

  /** DNS servers to use */
  dnsServers: string[];

  /** Spotlight directories to exclude from indexing */
  spotlightExclusions: string[];

  /** Services to keep disabled */
  disabledServices: string[];

  /** AI stack ports for health checking */
  aiStackPorts: {
    ollama: number;
    lmstudio: number;
    mlx: number;
  };
}

const DEFAULT_CONFIG: OptiMacConfig = {
  protectedProcesses: [
    "ollama",
    "lmstudio",
    "LM Studio",
    "mlx",
    "python3",
    "python",
    "node",
    "claude",
    "openclaw",
    "sshd",
    "WindowServer",
    "loginwindow",
    "launchd",
    "kernel_task",
    "mds_stores",
    "coreaudiod",
    "systemsoundserverd",
  ],

  memoryWarningThreshold: 0.75,
  memoryCriticalThreshold: 0.90,
  autoKillAtCritical: true,
  maxProcessRSSMB: 2048,
  maintenanceIntervalSec: 21600, // 6 hours

  dnsServers: ["1.1.1.1", "1.0.0.1"],

  spotlightExclusions: [
    "~/.ollama",
    "~/models",
    "~/.cache",
    "~/Library/Caches",
  ],

  disabledServices: [
    "com.apple.Siri.agent",
    "com.apple.notificationcenterui.agent",
    "com.apple.bird",
    "com.apple.AirPlayXPCHelper",
    "com.apple.photoanalysisd",
    "com.apple.mediaanalysisd",
    "com.apple.suggestd",
    "com.apple.assistantd",
    "com.apple.parsec-fbf",
    "com.apple.knowledge-agent",
  ],

  aiStackPorts: {
    ollama: 11434,
    lmstudio: 1234,
    mlx: 8080,
  },
};

export function loadConfig(): OptiMacConfig {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }

  if (!existsSync(CONFIG_FILE)) {
    saveConfig(DEFAULT_CONFIG);
    return { ...DEFAULT_CONFIG };
  }

  try {
    const raw = readFileSync(CONFIG_FILE, "utf-8");
    const parsed = JSON.parse(raw) as Partial<OptiMacConfig>;
    return { ...DEFAULT_CONFIG, ...parsed };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function saveConfig(config: OptiMacConfig): void {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), "utf-8");
}

export function isProcessProtected(processName: string, config: OptiMacConfig): boolean {
  const lower = processName.toLowerCase();
  return config.protectedProcesses.some((p) => lower.includes(p.toLowerCase()));
}
