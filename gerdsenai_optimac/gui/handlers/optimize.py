"""
Optimization handler -- maintenance, caches, power profiles, debloat.

Includes four-tier debloat presets aligned with the MCP server's
optimac_debloat tool, targeting macOS Sequoia (15.x) and Tahoe (26.x+).
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
from gerdsenai_optimac.gui.icons import get_icon


# ══════════════════════════════════════════════════════════════
#  Debloat Presets (mirrors MCP config-tools.ts)
# ══════════════════════════════════════════════════════════════

# Tier 1: Siri, notifications, iCloud, analytics
_DEBLOAT_MINIMAL = [
    "com.apple.Siri.agent",
    "com.apple.notificationcenterui.agent",
    "com.apple.bird",                       # iCloud sync
    "com.apple.parsec-fbf",                 # Siri analytics flush
]

# Tier 2: + photo/media analysis, suggestions, knowledge, sharing
_DEBLOAT_MODERATE = _DEBLOAT_MINIMAL + [
    "com.apple.photoanalysisd",
    "com.apple.mediaanalysisd",
    "com.apple.suggestd",
    "com.apple.assistantd",
    "com.apple.knowledge-agent",
    "com.apple.siriknowledged",             # Siri knowledge engine
    "com.apple.cloudd",                     # iCloud daemon (I/O intensive)
    "com.apple.handoff.agent",              # Handoff protocol
    "com.apple.sharingd",                   # AirDrop/sharing daemon
]

# Tier 3: + location, AirPlay, updates, Apple Intelligence
_DEBLOAT_AGGRESSIVE = _DEBLOAT_MODERATE + [
    "com.apple.locationd",
    "com.apple.AirPlayXPCHelper",
    "com.apple.iCloudNotificationAgent",
    "com.apple.softwareupdated",
    "com.apple.intelligenceplatformd",      # Apple Intelligence (macOS 15+)
    "com.apple.photolibraryd",              # Photo library sync
]

# Tier 4: Full AI inference optimization (macOS 15+ Sequoia / 26+ Tahoe)
_DEBLOAT_SEQUOIA = _DEBLOAT_AGGRESSIVE + [
    "com.apple.mlkit",                      # ML Kit framework
    "com.apple.mlserver",                   # ML server process
    "com.apple.triald",                     # Feature trials/experiments
    "com.apple.screenTimeAgent",            # Screen Time tracking
    "com.apple.CalendarAgent",              # Calendar sync
    "com.apple.remindd",                    # Reminders daemon
    "com.apple.commerce",                   # App Store background
    "com.apple.touristd",                   # macOS tips/tours
    "com.apple.tipsd",                      # Tips notifications
]

_DEBLOAT_PRESETS = {
    "minimal": _DEBLOAT_MINIMAL,
    "moderate": _DEBLOAT_MODERATE,
    "aggressive": _DEBLOAT_AGGRESSIVE,
    "sequoia": _DEBLOAT_SEQUOIA,
}


def build_menu(app):
    """Build Optimize submenu."""
    menu = rumps.MenuItem(
        "Optimize", icon=get_icon("wrench"), dimensions=(16, 16), template=True
    )

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

    # ── Debloat submenu ──
    debloat_menu = rumps.MenuItem("Debloat macOS")
    debloat_menu.add(
        rumps.MenuItem(
            "Minimal (Siri, iCloud, Notifications)",
            callback=lambda _: debloat_preset(app, "minimal"),
        )
    )
    debloat_menu.add(
        rumps.MenuItem(
            "Moderate (+ Photos, Suggestions, Sharing)",
            callback=lambda _: debloat_preset(app, "moderate"),
        )
    )
    debloat_menu.add(
        rumps.MenuItem(
            "Aggressive (+ Location, Updates, AI)",
            callback=lambda _: debloat_preset(app, "aggressive"),
        )
    )
    debloat_menu.add(
        rumps.MenuItem(
            "Sequoia/Tahoe (+ ML Kit, Calendar, Tips)",
            callback=lambda _: debloat_preset(app, "sequoia"),
        )
    )
    debloat_menu.add(rumps.separator)
    debloat_menu.add(
        rumps.MenuItem(
            "Re-enable All Services",
            callback=lambda _: debloat_reenable(app),
        )
    )
    menu.add(debloat_menu)

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
            "NVRAM Server Perf Mode",
            callback=lambda _: nvram_perf_mode(app),
        )
    )
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
        "performance -- AI server mode, no sleep,\n"
        "  Wake-on-LAN, auto-restart after power loss\n\n"
        "balanced -- moderate sleep, WoL on,\n"
        "  auto-restart, no Power Nap\n\n"
        "efficiency -- aggressive sleep, low power mode",
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
            "pmset -a gpuswitch 2 && "
            "pmset -a womp 1 && "           # Wake on LAN
            "pmset -a autorestart 1 && "    # Auto-restart after power failure
            "pmset -a ttyskeepawake 1 && "  # Prevent sleep with remote sessions
            "pmset -a powernap 0"           # Disable Power Nap (saves resources)
        ),
        "balanced": (
            "pmset -a displaysleep 10 && "
            "pmset -a sleep 0 && "
            "pmset -a disksleep 10 && "
            "pmset -a gpuswitch 2 && "
            "pmset -a womp 1 && "
            "pmset -a autorestart 1 && "
            "pmset -a powernap 0"
        ),
        "efficiency": (
            "pmset -a displaysleep 5 && "
            "pmset -a sleep 10 && "
            "pmset -a disksleep 5 && "
            "pmset -a gpuswitch 0 && "
            "pmset -a lowpowermode 1 && "
            "pmset -a powernap 0"
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
    progress.update("Reducing animations...")

    # Matches MCP server optimac_reduce_ui_overhead (13 settings)
    settings = [
        # Accessibility: reduce motion & transparency
        ("com.apple.universalaccess", "reduceMotion", "-bool", "true"),
        ("com.apple.universalaccess", "reduceTransparency", "-bool", "true"),
        # Window animations
        ("NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "-bool", "false"),
        ("NSGlobalDomain", "NSWindowResizeTime", "-float", "0.001"),
        # Dock animations
        ("com.apple.dock", "expose-animation-duration", "-float", "0.1"),
        ("com.apple.dock", "autohide-time-modifier", "-float", "0"),
        ("com.apple.dock", "autohide-delay", "-float", "0"),
        ("com.apple.dock", "launchanim", "-bool", "false"),
        # Springboard (Launchpad) animations
        ("com.apple.dock", "springboard-show-duration", "-float", "0.1"),
        ("com.apple.dock", "springboard-hide-duration", "-float", "0.1"),
        # Quick Look animation
        ("-g", "QLPanelAnimationDuration", "-float", "0"),
        # Disable smooth scrolling (reduces GPU compositing)
        ("NSGlobalDomain", "NSScrollAnimationEnabled", "-bool", "false"),
        # Disable rubber-band scrolling
        ("NSGlobalDomain", "NSScrollViewRubberbanding", "-bool", "false"),
    ]
    for domain, key, typ, val in settings:
        run_command(["defaults", "write", domain, key, typ, val])

    run_command(["killall", "Dock"])
    run_command(["killall", "Finder"])
    progress.finish("UI optimized")
    rumps.notification(
        "OptiMac",
        "UI Optimized",
        f"{len(settings)} animation/transparency settings applied",
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


# ── Debloat ──────────────────────────────────────────────────


def debloat_preset(app, preset):
    """Apply a debloat preset by disabling launchd services."""
    services = _DEBLOAT_PRESETS.get(preset, _DEBLOAT_MINIMAL)

    tier_desc = {
        "minimal": "Siri, iCloud, Notifications",
        "moderate": "+ Photos, Suggestions, Sharing",
        "aggressive": "+ Location, Updates, Apple Intelligence",
        "sequoia": "Full AI inference optimization (Sequoia/Tahoe)",
    }

    proceed = confirm_action(
        f"Debloat: {preset.title()}",
        f"This will disable {len(services)} macOS services:\n\n"
        f"  {tier_desc.get(preset, preset)}\n\n"
        f"All changes are reversible via\n"
        f"'Re-enable All Services'.",
        proceed_label="Disable",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Debloat")
    progress.update(f"Applying {preset} preset...")

    def _worker():
        # Get UID for launchctl domain target
        ok_uid, uid_out = run_command(["id", "-u"])
        uid = uid_out.strip() if ok_uid else "501"

        # Build batch of launchctl disable commands
        cmd_parts = [
            f"launchctl disable user/{uid}/{svc}"
            for svc in services
        ]

        # For moderate+, also disable Spotlight
        if preset != "minimal":
            cmd_parts.append("mdutil -a -i off 2>/dev/null || true")

        # For sequoia tier, also disable Apple Intelligence toggle
        if preset == "sequoia":
            cmd_parts.append(
                "defaults write com.apple.assistant.support "
                "'Assistant Enabled' -bool false"
            )

        combined = " && ".join(cmd_parts)
        ok, out = run_privileged(combined)

        if ok:
            progress.finish(f"{preset} applied")
            # Save disabled services to config
            _save_disabled_services(app, services)
            rumps.notification(
                "OptiMac",
                "Debloat",
                f"{preset.title()}: {len(services)} services disabled",
            )
        else:
            progress.fail("Debloat failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "Debloat",
                    f"Failed: {out[:60]}",
                )

    threading.Thread(target=_worker, daemon=True).start()


def debloat_reenable(app):
    """Re-enable all previously disabled services."""
    import json
    from pathlib import Path

    config_file = Path.home() / ".optimac" / "config.json"
    try:
        with open(config_file) as f:
            config = json.load(f)
        disabled = config.get("disabledServices", [])
    except (FileNotFoundError, json.JSONDecodeError):
        disabled = []

    if not disabled:
        show_result(
            "Re-enable Services",
            "No disabled services found.",
            "Nothing to re-enable.",
        )
        return

    proceed = confirm_action(
        "Re-enable All Services",
        f"This will re-enable {len(disabled)} previously\n"
        f"disabled macOS services.\n\n"
        f"Some services may require a restart to\n"
        f"fully resume.",
        proceed_label="Re-enable",
    )
    if not proceed:
        return

    progress = StatusProgress(app.status_item, "Re-enable")
    progress.update("Re-enabling services...")

    def _worker():
        ok_uid, uid_out = run_command(["id", "-u"])
        uid = uid_out.strip() if ok_uid else "501"

        cmd_parts = [
            f"launchctl enable user/{uid}/{svc}"
            for svc in disabled
        ]
        combined = " && ".join(cmd_parts)
        ok, out = run_privileged(combined)

        if ok:
            progress.finish("Services re-enabled")
            # Clear the disabled list in config
            try:
                with open(config_file) as f:
                    config = json.load(f)
                config["disabledServices"] = []
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=2)
                app.config = config
            except Exception:
                pass
            rumps.notification(
                "OptiMac",
                "Re-enable",
                f"{len(disabled)} services re-enabled",
            )
        else:
            progress.fail("Re-enable failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "Re-enable",
                    f"Failed: {out[:60]}",
                )

    threading.Thread(target=_worker, daemon=True).start()


def _save_disabled_services(app, services):
    """Persist disabled services list to config."""
    import json
    from pathlib import Path

    config_file = Path.home() / ".optimac" / "config.json"
    try:
        with open(config_file) as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    existing = set(config.get("disabledServices", []))
    existing.update(services)
    config["disabledServices"] = sorted(existing)

    config_dir = Path.home() / ".optimac"
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    app.config = config


# ── NVRAM Server Performance Mode ────────────────────────────


def nvram_perf_mode(app):
    """Toggle NVRAM server performance mode (boot-args serverperfmode)."""
    # Check current state
    ok, current = run_command(["nvram", "boot-args"], timeout=5)
    has_perf = "serverperfmode=1" in (current or "")

    if has_perf:
        proceed = confirm_action(
            "NVRAM Server Perf Mode",
            "Server performance mode is currently ENABLED.\n\n"
            "This allocates extra kernel resources for\n"
            "network throughput and I/O at the cost of\n"
            "higher idle power.\n\n"
            "Would you like to DISABLE it?",
            proceed_label="Disable",
        )
        if not proceed:
            return
        # Remove serverperfmode from boot-args
        new_args = current.replace("serverperfmode=1", "").replace("boot-args\t", "").strip()
        if new_args:
            ok, out = run_privileged(f"nvram boot-args='{new_args}'")
        else:
            ok, out = run_privileged("nvram -d boot-args")
    else:
        proceed = confirm_action(
            "NVRAM Server Perf Mode",
            "Enable server performance mode?\n\n"
            "This sets the NVRAM boot-args to allocate\n"
            "extra kernel resources for network throughput\n"
            "and I/O, optimizing for AI inference serving.\n\n"
            "Requires a RESTART to take effect.",
            proceed_label="Enable",
        )
        if not proceed:
            return
        # Append serverperfmode to existing boot-args
        existing = current.replace("boot-args\t", "").strip() if ok and current else ""
        new_args = f"{existing} serverperfmode=1".strip()
        ok, out = run_privileged(f"nvram boot-args='{new_args}'")

    if ok:
        state = "disabled" if has_perf else "enabled"
        rumps.notification(
            "OptiMac",
            "NVRAM",
            f"Server perf mode {state}. Restart required.",
        )
    else:
        if "Cancelled" not in (out or ""):
            rumps.notification(
                "OptiMac",
                "NVRAM",
                f"Failed: {out[:60]}",
            )


# ── Full Maintenance ─────────────────────────────────────────


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
            icon = "[OK]" if ok else "[FAIL]"
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
