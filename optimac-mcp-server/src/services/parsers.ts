/**
 * Parsers for macOS system command output.
 * Each parser takes raw stdout and returns structured data.
 */

export interface MemoryStats {
  pageSize: number;
  freePages: number;
  activePages: number;
  inactivePages: number;
  speculativePages: number;
  wiredPages: number;
  compressedPages: number;
  purgeablePages: number;
  fileBacked: number;
  anonymous: number;
  swapUsedMB: number;
  totalPhysicalMB: number;
  usedMB: number;
  freeMB: number;
  pressureLevel: "nominal" | "warning" | "critical";
}

export function parseVmStat(vmStatOutput: string, sysctl: string): MemoryStats {
  const lines = vmStatOutput.split("\n");
  const vals: Record<string, number> = {};

  // Parse actual page size from header: "Mach Virtual Memory Statistics: (page size of NNNNN bytes)"
  let pageSize = 16384; // Apple Silicon default
  const headerMatch = vmStatOutput.match(/page size of (\d+) bytes/);
  if (headerMatch) {
    pageSize = parseInt(headerMatch[1], 10);
  } else {
    // Fallback: try sysctl hw.pagesize
    const pageSizeMatch = sysctl.match(/hw\.pagesize:\s*(\d+)/);
    if (pageSizeMatch) pageSize = parseInt(pageSizeMatch[1], 10);
  }

  for (const line of lines) {
    const match = line.match(/^(.+?):\s+([\d.]+)/);
    if (match) {
      const key = match[1].trim().toLowerCase().replace(/[^a-z0-9]/g, "_");
      vals[key] = parseInt(match[2], 10);
    }
  }

  // Extract total physical memory from sysctl
  const memMatch = sysctl.match(/hw\.memsize:\s*(\d+)/);
  const totalBytes = memMatch ? parseInt(memMatch[1], 10) : 16 * 1024 * 1024 * 1024;
  const totalMB = Math.round(totalBytes / (1024 * 1024));

  const free = (vals["pages_free"] ?? 0) * pageSize;
  const active = (vals["pages_active"] ?? 0) * pageSize;
  const inactive = (vals["pages_inactive"] ?? 0) * pageSize;
  const speculative = (vals["pages_speculative"] ?? 0) * pageSize;
  const wired = (vals["pages_wired_down"] ?? 0) * pageSize;
  const compressed = (vals["pages_occupied_by_compressor"] ?? 0) * pageSize;
  const purgeable = (vals["pages_purgeable"] ?? 0) * pageSize;
  const fileBacked = (vals["file_backed_pages"] ?? 0) * pageSize;
  const anonymous = (vals["anonymous_pages"] ?? 0) * pageSize;

  // Match macOS Activity Monitor: used = app memory + wired + compressed
  // app memory ~ active (anonymous), wired = kernel, compressed = compressor-occupied
  const usedBytes = active + wired + compressed;
  const freeBytes = totalBytes - usedBytes;

  // Determine pressure level
  let pressureLevel: "nominal" | "warning" | "critical" = "nominal";
  const usedPercent = usedBytes / totalBytes;
  if (usedPercent > 0.90) pressureLevel = "critical";
  else if (usedPercent > 0.75) pressureLevel = "warning";

  return {
    pageSize,
    freePages: vals["pages_free"] ?? 0,
    activePages: vals["pages_active"] ?? 0,
    inactivePages: vals["pages_inactive"] ?? 0,
    speculativePages: vals["pages_speculative"] ?? 0,
    wiredPages: vals["pages_wired_down"] ?? 0,
    compressedPages: vals["pages_occupied_by_compressor"] ?? 0,
    purgeablePages: vals["pages_purgeable"] ?? 0,
    fileBacked: Math.round(fileBacked / (1024 * 1024)),
    anonymous: Math.round(anonymous / (1024 * 1024)),
    swapUsedMB: 0, // Populated from sysctl vm.swapusage if available
    totalPhysicalMB: totalMB,
    usedMB: Math.round(usedBytes / (1024 * 1024)),
    freeMB: Math.round(freeBytes / (1024 * 1024)),
    pressureLevel,
  };
}

export interface ProcessInfo {
  pid: number;
  user: string;
  cpuPercent: number;
  memPercent: number;
  rssMB: number;
  vsizeMB: number;
  state: string;
  command: string;
}

export function parseProcessList(psOutput: string): ProcessInfo[] {
  const lines = psOutput.split("\n").slice(1); // skip header
  const processes: ProcessInfo[] = [];

  for (const line of lines) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 11) continue;

    processes.push({
      pid: parseInt(parts[0], 10),
      user: parts[1],
      cpuPercent: parseFloat(parts[2]),
      memPercent: parseFloat(parts[3]),
      rssMB: Math.round(parseInt(parts[5], 10) / 1024),
      vsizeMB: Math.round(parseInt(parts[4], 10) / 1024),
      state: parts[7],
      command: parts.slice(10).join(" "),
    });
  }

  return processes.sort((a, b) => b.rssMB - a.rssMB);
}

export interface DiskUsage {
  filesystem: string;
  sizeMB: number;
  usedMB: number;
  availableMB: number;
  usedPercent: number;
  mountPoint: string;
}

export function parseDiskUsage(dfOutput: string): DiskUsage[] {
  const lines = dfOutput.split("\n").slice(1);
  const disks: DiskUsage[] = [];

  for (const line of lines) {
    const parts = line.trim().split(/\s+/);
    // macOS df -k has 9 columns: Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted
    if (parts.length < 9) continue;

    const sizeBlocks = parseInt(parts[1], 10);
    const usedBlocks = parseInt(parts[2], 10);
    const availBlocks = parseInt(parts[3], 10);
    const percent = parseInt(parts[4].replace("%", ""), 10);

    disks.push({
      filesystem: parts[0],
      sizeMB: Math.round(sizeBlocks / 1024), // 1024-byte blocks (df -k) to MB
      usedMB: Math.round(usedBlocks / 1024),
      availableMB: Math.round(availBlocks / 1024),
      usedPercent: percent,
      mountPoint: parts.slice(8).join(" "), // Mount point is column 9+
    });
  }

  return disks;
}

export interface NetworkInterface {
  name: string;
  ipv4: string;
  ipv6: string;
  status: "active" | "inactive";
}

export function parseNetworkInterfaces(ifconfigOutput: string): NetworkInterface[] {
  const interfaces: NetworkInterface[] = [];
  const blocks = ifconfigOutput.split(/^(?=\S)/m);

  for (const block of blocks) {
    const nameMatch = block.match(/^(\w+):/);
    if (!nameMatch) continue;

    const name = nameMatch[1];
    if (name === "lo0") continue; // skip loopback

    const ipv4Match = block.match(/inet\s+([\d.]+)/);
    const ipv6Match = block.match(/inet6\s+([\da-f:]+)/);
    const statusMatch = block.match(/status:\s+(\w+)/);

    interfaces.push({
      name,
      ipv4: ipv4Match?.[1] ?? "",
      ipv6: ipv6Match?.[1] ?? "",
      status: statusMatch?.[1] === "active" ? "active" : "inactive",
    });
  }

  return interfaces;
}

export interface ThermalInfo {
  cpuTempC: number;
  gpuTempC: number;
  throttled: boolean;
  fanSpeedRPM: number;
}

export function parsePowerMetrics(output: string): Partial<ThermalInfo> {
  const info: Partial<ThermalInfo> = {};

  const cpuTemp = output.match(/CPU die temperature:\s*([\d.]+)/);
  if (cpuTemp) info.cpuTempC = parseFloat(cpuTemp[1]);

  const gpuTemp = output.match(/GPU die temperature:\s*([\d.]+)/);
  if (gpuTemp) info.gpuTempC = parseFloat(gpuTemp[1]);

  const throttle = output.match(/CPU Speed Limit:\s*(\d+)/);
  if (throttle) info.throttled = parseInt(throttle[1], 10) < 100;

  return info;
}

export interface PMSetSettings {
  [key: string]: string | number;
}

export function parsePMSet(output: string): PMSetSettings {
  const settings: PMSetSettings = {};
  const lines = output.split("\n");

  for (const line of lines) {
    const match = line.match(/^\s+(\w+)\s+(\S+)/);
    if (match) {
      const val = parseInt(match[2], 10);
      settings[match[1]] = isNaN(val) ? match[2] : val;
    }
  }

  return settings;
}

export interface ServiceInfo {
  label: string;
  pid: number | null;
  status: number | null;
}

export function parseLaunchctlList(output: string): ServiceInfo[] {
  const lines = output.split("\n").slice(1);
  const services: ServiceInfo[] = [];

  for (const line of lines) {
    const parts = line.trim().split(/\t/);
    if (parts.length < 3) continue;

    services.push({
      pid: parts[0] === "-" ? null : parseInt(parts[0], 10),
      status: parts[1] === "-" ? null : parseInt(parts[1], 10),
      label: parts[2],
    });
  }

  return services;
}
