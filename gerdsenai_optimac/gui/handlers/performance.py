"""
Performance & Diagnostics handler — memory, disk, battery, thermal.
"""

import rumps
import psutil

from gerdsenai_optimac.gui.commands import run_command
from gerdsenai_optimac.gui.dialogs import show_result, StatusProgress
from gerdsenai_optimac.gui.monitors import get_compressed_memory_bytes
from gerdsenai_optimac.gui.sudo import run_privileged


def build_menu(app):
    """Build Performance submenu."""
    menu = rumps.MenuItem("📊 Performance")

    menu.add(
        rumps.MenuItem(
            "Check Memory Pressure",
            callback=lambda _: check_memory(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Purge Memory",
            callback=lambda _: purge_memory(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Disk Usage",
            callback=lambda _: disk_usage(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Battery Health",
            callback=lambda _: battery_health(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Thermal Status",
            callback=lambda _: thermal_status(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "I/O Statistics",
            callback=lambda _: io_stats(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Uptime & Load",
            callback=lambda _: uptime_load(app),
        )
    )
    return menu


# ── Tier 1 — Informational ────────────────────────────────────


def check_memory(app):
    mem = psutil.virtual_memory()
    compressed = get_compressed_memory_bytes()
    total_gb = mem.total / (1024**3)
    used_gb = mem.used / (1024**3)
    compressed_gb = compressed / (1024**3)
    avail_gb = mem.available / (1024**3)
    pct = mem.percent

    if pct < 75:
        pressure = "NOMINAL ●"
    elif pct < 90:
        pressure = "WARNING ▲"
    else:
        pressure = "CRITICAL ■"

    swap = psutil.swap_memory()
    swap_gb = swap.total / (1024**3)
    swap_used = swap.used / (1024**3)

    body = (
        f"  Pressure:    {pressure}\n"
        f"  Used:        {used_gb:.1f} GB / {total_gb:.1f} GB"
        f" ({pct:.0f}%)\n"
        f"  Compressed:  {compressed_gb:.1f} GB\n"
        f"  Available:   {avail_gb:.1f} GB\n"
        f"  Swap:        {swap_used:.1f} GB / {swap_gb:.1f} GB"
    )
    show_result("Memory Pressure", "Current memory state:", body)


def disk_usage(app):
    progress = StatusProgress(app.status_item, "Disk")
    progress.update("Scanning disk usage…")

    partitions = psutil.disk_partitions(all=False)
    lines = []
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            total = usage.total / (1024**3)
            used = usage.used / (1024**3)
            pct = usage.percent
            lines.append(
                f"  {p.mountpoint:<20} " f"{used:.1f} / {total:.1f} GB ({pct}%)"
            )
        except (PermissionError, OSError):
            pass

    # Add key user directories
    from pathlib import Path

    home = Path.home()
    for name, path in [
        ("~/Downloads", home / "Downloads"),
        ("~/Library/Caches", home / "Library" / "Caches"),
        ("~/Library", home / "Library"),
        ("~/.ollama", home / ".ollama"),
    ]:
        if path.exists():
            ok, out = run_command(
                ["du", "-sh", str(path)],
                timeout=15,
            )
            if ok:
                size = out.split()[0]
                lines.append(f"  {name:<20} {size}")

    progress.finish()
    show_result(
        "Disk Usage",
        "Storage breakdown:",
        "\n".join(lines) if lines else "No disks found",
    )


def battery_health(app):
    ok, out = run_command(
        [
            "system_profiler",
            "SPPowerDataType",
        ],
        timeout=15,
    )
    if not ok:
        show_result(
            "Battery",
            "Could not read battery data",
            out or "system_profiler failed",
        )
        return

    # Extract key info
    lines = []
    keys = [
        "charge remaining",
        "fully charged",
        "charging",
        "cycle count",
        "condition",
        "maximum capacity",
        "voltage",
        "amperage",
        "wattage",
        "connected",
        "ac charger",
    ]
    for line in out.split("\n"):
        line_l = line.lower().strip()
        if any(k in line_l for k in keys):
            lines.append(f"  {line.strip()}")

    show_result(
        "Battery Health",
        "Power & battery status:",
        "\n".join(lines) if lines else out[:500],
    )


def thermal_status(app):
    # Try pmset thermal log
    ok, pmset_out = run_command(["pmset", "-g", "thermlog"])
    lines = []
    if ok and pmset_out:
        for line in pmset_out.split("\n")[:10]:
            lines.append(f"  {line.strip()}")

    # CPU temperature via powermetrics (needs sudo)
    ok2, pm_out = run_privileged("powermetrics --samplers smc -i 1000 -n 1")
    if ok2 and pm_out:
        for line in pm_out.split("\n"):
            line_l = line.lower()
            if any(
                k in line_l
                for k in [
                    "temperature",
                    "die temp",
                    "throttl",
                ]
            ):
                lines.append(f"  {line.strip()}")

    if not lines:
        lines.append("  No thermal data available")
        lines.append("  (powermetrics may need admin access)")

    show_result(
        "Thermal Status",
        "System thermal state:",
        "\n".join(lines),
    )


def io_stats(app):
    counters = psutil.disk_io_counters()
    if counters:
        read_gb = counters.read_bytes / (1024**3)
        write_gb = counters.write_bytes / (1024**3)
        body = (
            f"  Read:       {read_gb:.2f} GB"
            f"  ({counters.read_count:,} ops)\n"
            f"  Written:    {write_gb:.2f} GB"
            f"  ({counters.write_count:,} ops)\n"
            f"  Read time:  {counters.read_time:,} ms\n"
            f"  Write time: {counters.write_time:,} ms"
        )
    else:
        body = "  Disk I/O counters not available"

    show_result("I/O Statistics", "Disk I/O since boot:", body)


def uptime_load(app):
    import time as _time

    boot = psutil.boot_time()
    uptime_s = _time.time() - boot
    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    mins = int((uptime_s % 3600) // 60)

    cpu_count = psutil.cpu_count()
    load_1, load_5, load_15 = psutil.getloadavg()
    cpu_pct = psutil.cpu_percent(interval=0.5)

    body = (
        f"  Uptime:      {days}d {hours}h {mins}m\n"
        f"  CPU Cores:   {cpu_count}\n"
        f"  CPU Usage:   {cpu_pct:.1f}%\n"
        f"  Load (1m):   {load_1:.2f}\n"
        f"  Load (5m):   {load_5:.2f}\n"
        f"  Load (15m):  {load_15:.2f}"
    )
    show_result("Uptime & Load", "System load averages:", body)


# ── Tier 3 — Privileged ───────────────────────────────────────


def purge_memory(app):
    progress = StatusProgress(app.status_item, "Purge")
    progress.update("Requesting authorization…")
    ok, out = run_privileged("purge")
    if ok:
        progress.finish("Memory purged")
        rumps.notification(
            "OptiMac",
            "Purge",
            "Memory purged successfully",
        )
    else:
        progress.fail("Purge failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "Purge",
                f"Failed: {out}",
            )
