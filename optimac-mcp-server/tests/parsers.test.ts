import { describe, it, expect } from "vitest";
import {
    parseVmStat,
    parseProcessList,
    parseDiskUsage,
    parseNetworkInterfaces,
    parsePowerMetrics,
    parsePMSet,
    parseLaunchctlList,
} from "../src/services/parsers.js";

// ---- Captured macOS outputs for realistic testing ----

const VM_STAT_OUTPUT = `Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               12345.
Pages active:                            234567.
Pages inactive:                           45678.
Pages speculative:                         1234.
Pages throttled:                              0.
Pages wired down:                         98765.
Pages purgeable:                           5432.
"Translation faults":                  12345678.
Pages copy-on-write:                     567890.
Pages zero filled:                      9876543.
Pages reactivated:                        12345.
Pages purged:                              6789.
File-backed pages:                        34567.
Anonymous pages:                          56789.
Pages stored in compressor:               23456.
Pages occupied by compressor:             11234.`;

const SYSCTL_OUTPUT = `hw.memsize: 17179869184
hw.pagesize: 16384
vm.swapusage: total = 2048.00M  used = 123.45M  free = 1924.55M`;

const SYSCTL_NO_SWAP = `hw.memsize: 17179869184
hw.pagesize: 16384`;

const SYSCTL_SWAP_GB = `hw.memsize: 34359738368
hw.pagesize: 16384
vm.swapusage: total = 4.00G  used = 1.50G  free = 2.50G`;

// ---- parseVmStat ----

describe("parseVmStat", () => {
    it("parses page size from header", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        expect(result.pageSize).toBe(16384);
    });

    it("falls back to sysctl for page size when header missing", () => {
        const noHeader = VM_STAT_OUTPUT.replace(
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)",
            "Mach Virtual Memory Statistics:"
        );
        const result = parseVmStat(noHeader, SYSCTL_OUTPUT);
        expect(result.pageSize).toBe(16384);
    });

    it("defaults to 16384 when no page size info available", () => {
        const noHeader = VM_STAT_OUTPUT.replace(
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)",
            "Mach Virtual Memory Statistics:"
        );
        const result = parseVmStat(noHeader, "hw.memsize: 17179869184");
        expect(result.pageSize).toBe(16384);
    });

    it("parses total physical memory from sysctl", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        expect(result.totalPhysicalMB).toBe(16384); // 16 GB
    });

    it("calculates used and free memory correctly", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        // used = (active + wired + compressed) * pageSize / (1024 * 1024)
        expect(result.usedMB).toBeGreaterThan(0);
        expect(result.freeMB).toBeGreaterThan(0);
        expect(result.usedMB + result.freeMB).toBe(result.totalPhysicalMB);
    });

    it("parses all page counts", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        expect(result.freePages).toBe(12345);
        expect(result.activePages).toBe(234567);
        expect(result.inactivePages).toBe(45678);
        expect(result.speculativePages).toBe(1234);
        expect(result.wiredPages).toBe(98765);
        expect(result.compressedPages).toBe(11234);
        expect(result.purgeablePages).toBe(5432);
    });

    it("parses swap usage in MB", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        expect(result.swapUsedMB).toBe(123); // 123.45M rounds to 123
    });

    it("parses swap usage in GB", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_SWAP_GB);
        expect(result.swapUsedMB).toBe(1536); // 1.5G = 1536 MB
    });

    it("returns 0 swap when sysctl has no swap info", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_NO_SWAP);
        expect(result.swapUsedMB).toBe(0);
    });

    it("sets pressure level based on usage", () => {
        const result = parseVmStat(VM_STAT_OUTPUT, SYSCTL_OUTPUT);
        expect(["nominal", "warning", "critical"]).toContain(result.pressureLevel);
    });
});

// ---- parseProcessList ----

const PS_OUTPUT = `  PID USER       %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND
  123 root         5.0  1.2  4567890  12345   ??  Ss   Mon09AM   0:12.34 /usr/sbin/something
  456 gerdsenai   12.3  4.5  7890123  56789   ??  S    Mon10AM   1:23.45 /Applications/App.app/Contents/MacOS/App --flag
  789 gerdsenai    0.0  0.1   123456   1024   ??  S    Mon11AM   0:00.01 /usr/bin/simple`;

describe("parseProcessList", () => {
    it("parses process entries correctly", () => {
        const processes = parseProcessList(PS_OUTPUT);
        expect(processes.length).toBe(3);
    });

    it("skips the header line", () => {
        const processes = parseProcessList(PS_OUTPUT);
        expect(processes.every((p) => p.pid > 0)).toBe(true);
    });

    it("parses PID, user, CPU, memory correctly", () => {
        const processes = parseProcessList(PS_OUTPUT);
        const app = processes.find((p) => p.pid === 456);
        expect(app).toBeDefined();
        expect(app!.user).toBe("gerdsenai");
        expect(app!.cpuPercent).toBe(12.3);
        expect(app!.memPercent).toBe(4.5);
    });

    it("preserves full command with flags", () => {
        const processes = parseProcessList(PS_OUTPUT);
        const app = processes.find((p) => p.pid === 456);
        expect(app!.command).toContain("--flag");
    });

    it("sorts by RSS descending", () => {
        const processes = parseProcessList(PS_OUTPUT);
        for (let i = 1; i < processes.length; i++) {
            expect(processes[i - 1].rssMB).toBeGreaterThanOrEqual(processes[i].rssMB);
        }
    });

    it("converts RSS from KB to MB", () => {
        const processes = parseProcessList(PS_OUTPUT);
        const root = processes.find((p) => p.pid === 123);
        expect(root!.rssMB).toBe(Math.round(12345 / 1024));
    });

    it("handles empty input", () => {
        const processes = parseProcessList("  PID USER   %CPU %MEM   VSZ  RSS  TT STAT STARTED  TIME COMMAND");
        expect(processes).toEqual([]);
    });
});

// ---- parseDiskUsage ----

const DF_OUTPUT = `Filesystem                        1024-blocks      Used Available Capacity  iused    ifree %iused Mounted on
/dev/disk3s1s1                      228108824  14789432 198876792     7% 356289 488962080    0% /
devfs                                     406       406         0   100%    703        0  100% /dev
/dev/disk3s6                        228108824    262144 198876792     1%       1 488962080    0% /System/Volumes/VM
/dev/disk1s2                          5242880   3145728   2097152    60%      45    73728    0% /System/Volumes/xarts`;

describe("parseDiskUsage", () => {
    it("parses disk entries", () => {
        const disks = parseDiskUsage(DF_OUTPUT);
        expect(disks.length).toBe(4);
    });

    it("converts 1024-blocks to MB", () => {
        const disks = parseDiskUsage(DF_OUTPUT);
        const root = disks.find((d) => d.mountPoint === "/");
        expect(root).toBeDefined();
        expect(root!.sizeMB).toBe(Math.round(228108824 / 1024));
    });

    it("parses capacity percentage", () => {
        const disks = parseDiskUsage(DF_OUTPUT);
        const root = disks.find((d) => d.mountPoint === "/");
        expect(root!.usedPercent).toBe(7);
    });

    it("handles mount points with spaces", () => {
        const disks = parseDiskUsage(DF_OUTPUT);
        const vm = disks.find((d) => d.mountPoint.includes("VM"));
        expect(vm).toBeDefined();
        expect(vm!.mountPoint).toBe("/System/Volumes/VM");
    });
});

// ---- parseNetworkInterfaces ----

const IFCONFIG_OUTPUT = `lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	inet 127.0.0.1 netmask 0xff000000
	inet6 ::1 prefixlen 128
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	ether aa:bb:cc:dd:ee:ff
	inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255
	inet6 fe80::1234:5678:abcd:ef01 prefixlen 64 scopeid 0x4
	status: active
en1: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	ether 11:22:33:44:55:66
	status: inactive`;

describe("parseNetworkInterfaces", () => {
    it("skips loopback interface", () => {
        const interfaces = parseNetworkInterfaces(IFCONFIG_OUTPUT);
        expect(interfaces.find((i) => i.name === "lo0")).toBeUndefined();
    });

    it("parses active interface with IPv4", () => {
        const interfaces = parseNetworkInterfaces(IFCONFIG_OUTPUT);
        const en0 = interfaces.find((i) => i.name === "en0");
        expect(en0).toBeDefined();
        expect(en0!.ipv4).toBe("192.168.1.100");
        expect(en0!.status).toBe("active");
    });

    it("parses IPv6 address", () => {
        const interfaces = parseNetworkInterfaces(IFCONFIG_OUTPUT);
        const en0 = interfaces.find((i) => i.name === "en0");
        expect(en0!.ipv6).toContain("fe80");
    });

    it("marks inactive interfaces", () => {
        const interfaces = parseNetworkInterfaces(IFCONFIG_OUTPUT);
        const en1 = interfaces.find((i) => i.name === "en1");
        expect(en1!.status).toBe("inactive");
    });

    it("handles interfaces without IP addresses", () => {
        const interfaces = parseNetworkInterfaces(IFCONFIG_OUTPUT);
        const en1 = interfaces.find((i) => i.name === "en1");
        expect(en1!.ipv4).toBe("");
    });
});

// ---- parsePowerMetrics ----

describe("parsePowerMetrics", () => {
    it("parses CPU temperature", () => {
        const result = parsePowerMetrics("CPU die temperature: 42.5 C");
        expect(result.cpuTempC).toBe(42.5);
    });

    it("parses GPU temperature", () => {
        const result = parsePowerMetrics("GPU die temperature: 38.2 C");
        expect(result.gpuTempC).toBe(38.2);
    });

    it("detects throttling when speed limit < 100", () => {
        const result = parsePowerMetrics("CPU Speed Limit: 80");
        expect(result.throttled).toBe(true);
    });

    it("detects no throttling at 100", () => {
        const result = parsePowerMetrics("CPU Speed Limit: 100");
        expect(result.throttled).toBe(false);
    });

    it("returns empty partial for unrecognized output", () => {
        const result = parsePowerMetrics("some random output");
        expect(result.cpuTempC).toBeUndefined();
        expect(result.gpuTempC).toBeUndefined();
        expect(result.throttled).toBeUndefined();
    });
});

// ---- parsePMSet ----

const PMSET_OUTPUT = `System-wide power settings:
Currently in use:
 standby              1
 Sleep On Power Button 1
 autorestart          0
 womp                 1
 hibernatemode        3
 displaysleep         10
 sleep                0
 disksleep            10`;

describe("parsePMSet", () => {
    it("parses numeric settings", () => {
        const settings = parsePMSet(PMSET_OUTPUT);
        expect(settings["standby"]).toBe(1);
        expect(settings["sleep"]).toBe(0);
        expect(settings["displaysleep"]).toBe(10);
    });

    it("parses all settings from output", () => {
        const settings = parsePMSet(PMSET_OUTPUT);
        expect(Object.keys(settings).length).toBeGreaterThanOrEqual(6);
    });
});

// ---- parseLaunchctlList ----

const LAUNCHCTL_OUTPUT = `PID	Status	Label
-	0	com.apple.some.service
12345	0	com.apple.running.service
-	78	com.apple.failed.service`;

describe("parseLaunchctlList", () => {
    it("parses service entries", () => {
        const services = parseLaunchctlList(LAUNCHCTL_OUTPUT);
        expect(services.length).toBe(3);
    });

    it("handles dash PID as null", () => {
        const services = parseLaunchctlList(LAUNCHCTL_OUTPUT);
        const notRunning = services.find((s) => s.label === "com.apple.some.service");
        expect(notRunning!.pid).toBeNull();
    });

    it("parses numeric PID", () => {
        const services = parseLaunchctlList(LAUNCHCTL_OUTPUT);
        const running = services.find((s) => s.label === "com.apple.running.service");
        expect(running!.pid).toBe(12345);
    });

    it("parses non-zero status", () => {
        const services = parseLaunchctlList(LAUNCHCTL_OUTPUT);
        const failed = services.find((s) => s.label === "com.apple.failed.service");
        expect(failed!.status).toBe(78);
    });
});
