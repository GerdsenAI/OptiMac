"""
System Control handler — process management, toggles, cleanup.
"""

import rumps

from gerdsenai_optimac.gui.commands import run_command
from gerdsenai_optimac.gui.dialogs import (
    show_result,
    confirm_action,
    StatusProgress,
)
from gerdsenai_optimac.gui.sudo import run_privileged


def build_menu(app):
    """Build System Control submenu."""
    menu = rumps.MenuItem("⚙️ System Control")

    menu.add(
        rumps.MenuItem(
            "Top Processes",
            callback=lambda _: top_processes(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Kill Process",
            callback=lambda _: kill_process(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Toggle Wi-Fi",
            callback=lambda _: toggle_wifi(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Toggle Bluetooth",
            callback=lambda _: toggle_bluetooth(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Login Items",
            callback=lambda _: login_items(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Eject All Drives",
            callback=lambda _: eject_all(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Lock Screen",
            callback=lambda _: lock_screen(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Restart Finder",
            callback=lambda _: restart_finder(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Restart Dock",
            callback=lambda _: restart_dock(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Empty Trash",
            callback=lambda _: empty_trash(app),
        )
    )
    return menu


# ── Tier 1 — Informational ────────────────────────────────────


def top_processes(app):
    import psutil

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sort by CPU first
    by_cpu = sorted(
        procs,
        key=lambda x: x.get("cpu_percent", 0) or 0,
        reverse=True,
    )[:10]

    by_mem = sorted(
        procs,
        key=lambda x: x.get("memory_percent", 0) or 0,
        reverse=True,
    )[:10]

    lines = ["── Top by CPU ──"]
    for p in by_cpu:
        cpu = p.get("cpu_percent", 0) or 0
        name = (p.get("name") or "?")[:24]
        pid = p.get("pid", "?")
        lines.append(f"  {cpu:>5.1f}%  {pid:>6}  {name}")

    lines.append("")
    lines.append("── Top by Memory ──")
    for p in by_mem:
        mem = p.get("memory_percent", 0) or 0
        name = (p.get("name") or "?")[:24]
        pid = p.get("pid", "?")
        lines.append(f"  {mem:>5.1f}%  {pid:>6}  {name}")

    show_result(
        "Top Processes",
        "System process usage:",
        "\n".join(lines),
    )


def login_items(app):
    ok, out = run_command(
        [
            "osascript",
            "-e",
            'tell application "System Events" to get the name' " of every login item",
        ]
    )
    if ok and out:
        items = [f"  • {i.strip()}" for i in out.split(",")]
        show_result(
            "Login Items",
            f"{len(items)} items launch at login:",
            "\n".join(items),
        )
    else:
        show_result(
            "Login Items",
            "Could not retrieve login items",
            out or "System Events access may be restricted",
        )


# ── Tier 4 — Destructive ──────────────────────────────────────


def kill_process(app):
    response = rumps.Window(
        "Enter process name or PID to terminate:",
        title="Kill Process",
        default_text="",
        ok="Kill",
        cancel="Cancel",
    ).run()
    if not response.clicked:
        return
    target = response.text.strip()
    if not target:
        return

    proceed = confirm_action(
        "Kill Process",
        f"Terminate process: {target}\n\n"
        f"This may cause data loss in the target app.",
        proceed_label="Kill",
    )
    if not proceed:
        return

    # Try as PID first, then by name
    if target.isdigit():
        ok, out = run_command(["kill", "-9", target])
    else:
        ok, out = run_command(["pkill", "-9", "-f", target])

    if ok:
        rumps.notification(
            "OptiMac",
            "Process",
            f"Terminated: {target}",
        )
    else:
        rumps.notification(
            "OptiMac",
            "Process",
            f"Failed: {out}",
        )


def eject_all(app):
    proceed = confirm_action(
        "Eject All External Drives",
        "This will unmount and eject all external\n"
        "drives and volumes.\n\n"
        "Make sure no files are in use.",
        proceed_label="Eject All",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Eject")
    progress.update("Ejecting drives…")
    ok, out = run_command(
        [
            "osascript",
            "-e",
            'tell application "Finder" to eject'
            " (every disk whose ejectable is true)",
        ]
    )
    if ok:
        progress.finish("All drives ejected")
        rumps.notification(
            "OptiMac",
            "Drives",
            "All external drives ejected",
        )
    else:
        progress.fail("Eject failed")
        rumps.notification(
            "OptiMac",
            "Drives",
            f"Failed: {out}",
        )


def empty_trash(app):
    proceed = confirm_action(
        "Empty Trash",
        "Permanently delete all items in Trash.\n\n" "This cannot be undone.",
        proceed_label="Empty Trash",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Trash")
    progress.update("Emptying Trash…")
    ok, out = run_command(
        [
            "osascript",
            "-e",
            'tell application "Finder" to empty trash',
        ]
    )
    if ok:
        progress.finish("Trash emptied")
        rumps.notification("OptiMac", "Trash", "Trash emptied")
    else:
        progress.fail("Empty Trash failed")
        rumps.notification(
            "OptiMac",
            "Trash",
            f"Failed: {out}",
        )


# ── Tier 2 — Safe Actions ─────────────────────────────────────


def toggle_wifi(app):
    # Detect current state
    ok, out = run_command(
        [
            "networksetup",
            "-getairportpower",
            "en0",
        ]
    )
    currently_on = "On" in (out or "")
    action = "off" if currently_on else "on"

    progress = StatusProgress(app.status_item, "Wi-Fi")
    progress.update(f"Turning Wi-Fi {action}…")
    run_command(
        [
            "networksetup",
            "-setairportpower",
            "en0",
            action,
        ]
    )
    progress.finish(f"Wi-Fi {action}")
    rumps.notification(
        "OptiMac",
        "Wi-Fi",
        f"Wi-Fi turned {action}",
    )


def toggle_bluetooth(app):
    # Check if blueutil is installed
    ok, _ = run_command(["which", "blueutil"])
    if not ok:
        show_result(
            "Bluetooth",
            "blueutil not installed",
            "Install with:\n  brew install blueutil",
        )
        return

    ok, out = run_command(["blueutil", "--power"])
    currently_on = out.strip() == "1"
    new_state = "0" if currently_on else "1"
    label = "off" if currently_on else "on"

    progress = StatusProgress(app.status_item, "Bluetooth")
    progress.update(f"Turning Bluetooth {label}…")
    run_command(["blueutil", "--power", new_state])
    progress.finish(f"Bluetooth {label}")
    rumps.notification(
        "OptiMac",
        "Bluetooth",
        f"Bluetooth turned {label}",
    )


def lock_screen(app):
    run_command(
        [
            "pmset",
            "displaysleepnow",
        ]
    )


def restart_finder(app):
    progress = StatusProgress(app.status_item, "Finder")
    progress.update("Restarting Finder…")
    run_command(["killall", "Finder"])
    progress.finish("Finder restarted")


def restart_dock(app):
    progress = StatusProgress(app.status_item, "Dock")
    progress.update("Restarting Dock…")
    run_command(["killall", "Dock"])
    progress.finish("Dock restarted")
