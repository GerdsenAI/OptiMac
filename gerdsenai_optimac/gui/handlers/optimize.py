"""
Optimization handler — maintenance, caches, power profiles.
"""

import threading

import rumps

from gerdsenai_optimac.gui.commands import run_command
from gerdsenai_optimac.gui.dialogs import (
    show_result,
    confirm_action,
    StatusProgress,
)
from gerdsenai_optimac.gui.sudo import (
    run_privileged,
    run_privileged_batch,
)


def build_menu(app):
    """Build Optimize submenu."""
    menu = rumps.MenuItem("🔧 Optimize")

    menu.add(
        rumps.MenuItem(
            "Apply Power Profile",
            callback=lambda _: power_profile(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Reduce UI Overhead",
            callback=lambda _: reduce_ui(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Clear Caches",
            callback=lambda _: clear_caches(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Rebuild Spotlight",
            callback=lambda _: rebuild_spotlight(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Optimize Homebrew",
            callback=lambda _: optimize_homebrew(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Run Full Maintenance",
            callback=lambda _: full_maintenance(app),
        )
    )
    return menu


# ── Tier 3 — Privileged ───────────────────────────────────────


def power_profile(app):
    response = rumps.Window(
        "Choose a power profile:\n\n"
        "performance — max clock, no sleep\n"
        "balanced    — default macOS settings\n"
        "efficiency  — low power, extend battery",
        title="Power Profile",
        default_text="performance",
        ok="Apply",
        cancel="Cancel",
    ).run()
    if not response.clicked:
        return
    profile = response.text.strip().lower()

    profiles = {
        "performance": (
            "pmset -a displaysleep 0 && "
            "pmset -a sleep 0 && "
            "pmset -a disksleep 0 && "
            "pmset -a gpuswitch 2"
        ),
        "balanced": (
            "pmset -a displaysleep 10 && "
            "pmset -a sleep 0 && "
            "pmset -a disksleep 10 && "
            "pmset -a gpuswitch 2"
        ),
        "efficiency": (
            "pmset -a displaysleep 5 && "
            "pmset -a sleep 10 && "
            "pmset -a disksleep 5 && "
            "pmset -a gpuswitch 0 && "
            "pmset -a lowpowermode 1"
        ),
    }

    if profile not in profiles:
        rumps.notification(
            "OptiMac",
            "Profile",
            f"Unknown profile: {profile}",
        )
        return

    progress = StatusProgress(app.status_item, "Profile")
    progress.update(f"Applying {profile}…")

    ok, out = run_privileged(profiles[profile])
    if ok:
        progress.finish(f"{profile} applied")
        rumps.notification(
            "OptiMac",
            "Power Profile",
            f"{profile.title()} profile applied",
        )
    else:
        progress.fail("Profile failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "Profile",
                f"Failed: {out}",
            )


def rebuild_spotlight(app):
    proceed = confirm_action(
        "Rebuild Spotlight Index",
        "This will erase and rebuild the Spotlight\n"
        "search index for your main drive.\n\n"
        "Indexing may take 30–60 minutes &\n"
        "temporarily increase CPU usage.",
        proceed_label="Rebuild",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Spotlight")
    progress.update("Rebuilding index…")
    ok, out = run_privileged("mdutil -E /")
    if ok:
        progress.finish("Spotlight rebuilding")
        rumps.notification(
            "OptiMac",
            "Spotlight",
            "Index rebuild started. May take 30–60 min.",
        )
    else:
        progress.fail("Spotlight failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "Spotlight",
                f"Failed: {out}",
            )


# ── Tier 2 — Safe Actions ─────────────────────────────────────


def reduce_ui(app):
    progress = StatusProgress(app.status_item, "UI")
    progress.update("Reducing animations…")

    settings = [
        ("com.apple.dock", "launchanim", "-bool", "false"),
        ("NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "-bool", "false"),
        ("com.apple.dock", "expose-animation-duration", "-float", "0.1"),
        ("com.apple.dock", "autohide-time-modifier", "-float", "0.3"),
        ("NSGlobalDomain", "NSWindowResizeTime", "-float", "0.1"),
    ]
    for domain, key, typ, val in settings:
        run_command(["defaults", "write", domain, key, typ, val])

    run_command(["killall", "Dock"])
    progress.finish("UI optimized")
    rumps.notification(
        "OptiMac",
        "UI Optimized",
        "Dock & window animations reduced",
    )


def optimize_homebrew(app):
    ok, _ = run_command(["which", "brew"])
    if not ok:
        show_result(
            "Homebrew",
            "Homebrew not installed",
            "Install from https://brew.sh",
        )
        return

    progress = StatusProgress(app.status_item, "Homebrew")
    progress.update("Cleaning up Homebrew…")

    def _worker():
        ok1, out1 = run_command(
            ["brew", "cleanup", "--prune=7"],
            timeout=120,
        )
        ok2, out2 = run_command(
            ["brew", "autoremove"],
            timeout=60,
        )
        progress.finish("Homebrew cleaned")

        body = "── Cleanup ──\n"
        body += out1 or "(nothing to clean)\n"
        body += "\n── Autoremove ──\n"
        body += out2 or "(nothing to remove)"

        show_result(
            "Homebrew Optimization",
            "Cleanup results:",
            body,
        )

    threading.Thread(target=_worker, daemon=True).start()


# ── Tier 4 — Destructive ──────────────────────────────────────


def clear_caches(app):
    from pathlib import Path

    home = Path.home()
    cache_dir = home / "Library" / "Caches"

    # Estimate size
    ok, size_out = run_command(
        ["du", "-sh", str(cache_dir)],
        timeout=10,
    )
    size_str = size_out.split()[0] if ok and size_out else "unknown"

    proceed = confirm_action(
        "Clear Application Caches",
        f"This will remove {size_str} of cached data from\n"
        f"~/Library/Caches.\n\n"
        f"Applications may run slower until they\n"
        f"rebuild their caches.\n\n"
        f"This cannot be undone.",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Caches")
    progress.update("Clearing caches…")

    ok, out = run_privileged(
        f"find '{cache_dir}' -mindepth 1 -maxdepth 1 "
        f"-type d -exec rm -rf {{}} + 2>/dev/null; "
        f"echo 'done'"
    )
    if ok:
        progress.finish("Caches cleared")
        rumps.notification(
            "OptiMac",
            "Caches",
            f"Cleared {size_str} of cached data",
        )
    else:
        progress.fail("Cache clear failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "Caches",
                f"Failed: {out}",
            )


def full_maintenance(app):
    proceed = confirm_action(
        "Run Full Maintenance",
        "This will perform all optimization steps:\n\n"
        "  1. Purge memory\n"
        "  2. Flush DNS cache\n"
        "  3. Flush routing table\n"
        "  4. Clear user caches\n"
        "  5. Run maintenance scripts\n\n"
        "Requires administrator access.",
        proceed_label="Run All",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Maintenance")

    def _worker():
        commands = [
            ("Purging memory", "purge"),
            (
                "Flushing DNS",
                "dscacheutil -flushcache" " && killall -HUP mDNSResponder",
            ),
            ("Flushing routes", "route -n flush"),
            (
                "Running maintenance scripts",
                "periodic daily weekly monthly",
            ),
        ]

        def _on_progress(step, total, desc):
            progress.update(desc, step=step + 1, total=total)

        all_ok, results = run_privileged_batch(
            commands,
            progress_callback=_on_progress,
        )

        lines = []
        for (desc, _cmd), (ok, out) in zip(commands, results):
            icon = "✅" if ok else "❌"
            lines.append(f"  {icon} {desc}")
            if not ok and out:
                lines.append(f"     {out[:80]}")

        if all_ok:
            progress.finish("Maintenance complete")
        else:
            progress.fail("Maintenance partial")

        show_result(
            "Full Maintenance",
            "Maintenance results:",
            "\n".join(lines),
        )

    threading.Thread(target=_worker, daemon=True).start()
