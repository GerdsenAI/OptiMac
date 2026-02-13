"""
Security & Cyber Defense handler — firewall, audits, intrusion detection.
"""

import threading

import rumps

from gerdsenai_optimac.gui.commands import run_command
from gerdsenai_optimac.gui.dialogs import show_result, StatusProgress
from gerdsenai_optimac.gui.sudo import run_privileged


def build_menu(app):
    """Build Security submenu."""
    menu = rumps.MenuItem("🛡️ Security")

    menu.add(
        rumps.MenuItem(
            "Security Overview",
            callback=lambda _: security_overview(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Firewall Status",
            callback=lambda _: firewall_status(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Toggle Firewall",
            callback=lambda _: toggle_firewall(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "SIP Status",
            callback=lambda _: sip_status(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Gatekeeper Status",
            callback=lambda _: gatekeeper_status(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "FileVault Status",
            callback=lambda _: filevault_status(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Open Ports Audit",
            callback=lambda _: open_ports_audit(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Unsigned Processes",
            callback=lambda _: unsigned_processes(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Failed Logins",
            callback=lambda _: failed_logins(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Connection Audit",
            callback=lambda _: connection_audit(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Malware Path Check",
            callback=lambda _: malware_check(app),
        )
    )
    return menu


# ── Security Overview ──────────────────────────────────────────


def security_overview(app):
    progress = StatusProgress(app.status_item, "Security")
    progress.update("Auditing security posture…")

    lines = []

    # SIP
    ok, out = run_command(["csrutil", "status"])
    if ok:
        sip_on = "enabled" in out.lower()
        lines.append(f"  SIP:         {'✅ Enabled' if sip_on else '⚠️  Disabled'}")

    # Gatekeeper
    ok, out = run_command(["spctl", "--status"])
    if ok:
        gk_on = "enabled" in out.lower()
        lines.append(f"  Gatekeeper:  {'✅ Enabled' if gk_on else '⚠️  Disabled'}")

    # FileVault
    ok, out = run_command(["fdesetup", "status"])
    if ok:
        fv_on = "on" in out.lower()
        lines.append(f"  FileVault:   {'✅ On' if fv_on else '⚠️  Off'}")

    # Firewall
    ok, out = run_privileged(
        "/usr/libexec/ApplicationFirewall/" "socketfilterfw --getglobalstate"
    )
    if ok:
        fw_on = "enabled" in out.lower()
        lines.append(f"  Firewall:    {'✅ Enabled' if fw_on else '⚠️  Disabled'}")
    else:
        lines.append("  Firewall:    ? (needs admin)")

    # Listening ports count
    ok, out = run_command(
        ["lsof", "-i", "-P", "-n"],
        timeout=10,
    )
    if ok and out:
        listen_count = sum(1 for line in out.split("\n") if "LISTEN" in line)
        lines.append(f"  Open Ports:  {listen_count} listening")

    progress.finish()
    show_result(
        "Security Overview",
        "System security posture:",
        "\n".join(lines),
    )


# ── Individual Status Checks ──────────────────────────────────


def firewall_status(app):
    ok, out = run_privileged(
        "/usr/libexec/ApplicationFirewall/" "socketfilterfw --getglobalstate"
    )
    if ok:
        enabled = "enabled" in out.lower()
        extra_lines = []
        # Get stealth mode
        ok2, stealth = run_privileged(
            "/usr/libexec/ApplicationFirewall/" "socketfilterfw --getstealthmode"
        )
        if ok2:
            extra_lines.append(f"  {stealth.strip()}")
        # Get block-all mode
        ok3, block = run_privileged(
            "/usr/libexec/ApplicationFirewall/" "socketfilterfw --getblockall"
        )
        if ok3:
            extra_lines.append(f"  {block.strip()}")

        body = f"  State:  {'ENABLED ✅' if enabled else 'DISABLED ⚠️'}\n" + "\n".join(
            extra_lines
        )
        show_result("Firewall", "Application Firewall:", body)
    else:
        if "Cancelled" not in (out or ""):
            show_result(
                "Firewall",
                "Could not check firewall",
                out or "Needs admin access",
            )


def toggle_firewall(app):
    # Check current state
    ok, out = run_privileged(
        "/usr/libexec/ApplicationFirewall/" "socketfilterfw --getglobalstate"
    )
    if not ok:
        if "Cancelled" not in (out or ""):
            show_result(
                "Firewall",
                "Could not read state",
                out or "Needs admin access",
            )
        return

    currently_on = "enabled" in out.lower()
    new_state = "off" if currently_on else "on"
    label = "Disable" if currently_on else "Enable"

    progress = StatusProgress(app.status_item, "Firewall")
    progress.update(f"{label}ing firewall…")

    ok, out = run_privileged(
        f"/usr/libexec/ApplicationFirewall/"
        f"socketfilterfw --setglobalstate {new_state}"
    )
    if ok:
        progress.finish(f"Firewall {new_state}")
        rumps.notification(
            "OptiMac",
            "Firewall",
            f"Firewall turned {new_state}",
        )
    else:
        progress.fail("Firewall toggle failed")
        if "Cancelled" not in (out or ""):
            rumps.notification(
                "OptiMac",
                "Firewall",
                f"Failed: {out}",
            )


def sip_status(app):
    ok, out = run_command(["csrutil", "status"])
    show_result(
        "System Integrity Protection",
        "SIP Status:",
        out if ok else "Could not check SIP status",
    )


def gatekeeper_status(app):
    ok, out = run_command(["spctl", "--status"])
    show_result(
        "Gatekeeper",
        "Gatekeeper Status:",
        out if ok else "Could not check Gatekeeper",
    )


def filevault_status(app):
    ok, out = run_command(["fdesetup", "status"])
    show_result(
        "FileVault",
        "FileVault Status:",
        out if ok else "Could not check FileVault",
    )


# ── Intelligence & Audit ───────────────────────────────────────


def open_ports_audit(app):
    progress = StatusProgress(app.status_item, "Audit")
    progress.update("Scanning open ports…")

    ok, out = run_command(
        ["lsof", "-i", "-P", "-n"],
        timeout=15,
    )
    progress.finish()

    if ok and out:
        lines = out.split("\n")
        listening = [line for line in lines if "LISTEN" in line]
        # Analyze for suspicious ports
        suspicious = []
        known_safe = {
            22,
            53,
            80,
            443,
            631,
            5000,
            5353,
            8080,
            8443,
            11434,
            1234,
            49152,
        }
        for line in listening:
            parts = line.split()
            if len(parts) >= 9:
                port_part = parts[8].split(":")
                try:
                    port = int(port_part[-1])
                    if port not in known_safe and port < 49152:
                        suspicious.append(f"  ⚠️  {parts[0]:<16} port {port}")
                except (ValueError, IndexError):
                    pass

        result = [f"  {len(listening)} ports listening\n"]
        if suspicious:
            result.append("── Unusual ports ──")
            result.extend(suspicious)
            result.append("")
        result.append("── All listening ──")
        for line in listening[:20]:
            result.append(f"  {line}")

        show_result(
            "Open Ports Audit",
            "Network port analysis:",
            "\n".join(result),
        )
    else:
        show_result(
            "Open Ports",
            "Could not scan",
            out or "lsof failed",
        )


def unsigned_processes(app):
    progress = StatusProgress(app.status_item, "Audit")
    progress.update("Checking code signatures…")

    def _worker():
        import psutil as _psutil

        unsigned = []
        checked = 0

        for proc in _psutil.process_iter(["pid", "name", "exe"]):
            try:
                exe = proc.info.get("exe")
                if not exe or not exe.startswith("/"):
                    continue
                checked += 1
                result = run_command(
                    ["codesign", "--verify", "--deep", exe],
                    timeout=5,
                )
                if not result[0]:
                    name = proc.info.get("name", "?")
                    pid = proc.info.get("pid", "?")
                    unsigned.append(f"  ⚠️  {name:<20} PID {pid}\n" f"      {exe}")
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                pass

            if checked > 50:
                break

        progress.finish()

        if unsigned:
            body = (
                f"  Checked {checked} processes.\n"
                f"  Found {len(unsigned)} unsigned:\n\n" + "\n".join(unsigned[:15])
            )
        else:
            body = (
                f"  Checked {checked} processes.\n"
                f"  All verified — no unsigned binaries found ✅"
            )

        show_result(
            "Unsigned Processes",
            "Code signature audit:",
            body,
        )

    threading.Thread(target=_worker, daemon=True).start()


def failed_logins(app):
    progress = StatusProgress(app.status_item, "Security")
    progress.update("Searching login failures…")

    def _worker():
        ok, out = run_command(
            [
                "log",
                "show",
                "--style",
                "compact",
                "--predicate",
                'eventMessage contains "authentication"'
                ' OR eventMessage contains "failed"'
                ' OR eventMessage contains "invalid"',
                "--last",
                "1h",
            ],
            timeout=30,
        )
        progress.finish()

        if ok and out:
            lines = out.strip().split("\n")
            count = len(
                [ln for ln in lines if "fail" in ln.lower() or "invalid" in ln.lower()]
            )
            body = f"  {count} suspicious entries in last hour\n\n" + "\n".join(
                lines[:25]
            )
            show_result(
                "Failed Logins",
                "Authentication events (last 1h):",
                body,
            )
        else:
            show_result(
                "Failed Logins",
                "No events found",
                "No authentication failures in the last hour ✅",
            )

    threading.Thread(target=_worker, daemon=True).start()


def connection_audit(app):
    progress = StatusProgress(app.status_item, "Intel")
    progress.update("Auditing foreign connections…")

    def _worker():
        ok, out = run_command(
            ["lsof", "-i", "-P", "-n"],
            timeout=15,
        )
        if not ok or not out:
            progress.finish()
            show_result(
                "Connection Audit",
                "Could not scan",
                out or "lsof failed",
            )
            return

        lines = out.split("\n")
        established = [line for line in lines if "ESTABLISHED" in line]

        foreign = []
        local_prefixes = (
            "127.",
            "10.",
            "172.",
            "192.168.",
            "::1",
            "fe80",
        )

        for conn in established:
            parts = conn.split()
            if len(parts) >= 9:
                remote = parts[8]
                ip = (
                    remote.split(":")[0]
                    .replace(
                        "->",
                        "",
                    )
                    .strip()
                )
                if ip and not any(ip.startswith(p) for p in local_prefixes):
                    proc = parts[0]
                    foreign.append(f"  {proc:<16} → {remote}")

        progress.finish()

        if foreign:
            body = (
                f"  {len(foreign)} foreign connection(s):\n\n"
                + "\n".join(foreign[:20])
                + "\n\n  Use 'whois <IP>' to investigate"
            )
        else:
            body = "  No foreign connections detected ✅\n" "  All traffic is local"

        show_result(
            "Connection Audit",
            "Foreign network connections:",
            body,
        )

    threading.Thread(target=_worker, daemon=True).start()


def malware_check(app):
    progress = StatusProgress(app.status_item, "Security")
    progress.update("Scanning for known malware…")

    def _worker():
        from pathlib import Path as _Path

        home = _Path.home()

        # Known macOS malware paths and indicators
        suspicious_paths = [
            home / "Library" / "LaunchAgents",
            _Path("/Library/LaunchAgents"),
            _Path("/Library/LaunchDaemons"),
            home / ".mitmproxy",
            home / ".proxy",
            home / "Library" / "Application Support" / "com.pcv",
            _Path("/private/tmp/.hidden"),
            home / ".local" / "share" / ".hidden",
        ]

        findings = []
        checked = 0

        for path in suspicious_paths:
            if not path.exists():
                continue

            if path.is_dir():
                try:
                    items = list(path.iterdir())
                    # Check for suspicious launch agents
                    for item in items:
                        checked += 1
                        name = item.name.lower()
                        # Flag non-Apple, non-standard items
                        if not name.startswith("com.apple") and item.suffix == ".plist":
                            findings.append(f"  📋 {item}")
                except PermissionError:
                    findings.append(f"  🔒 {path} (access denied)")
            else:
                checked += 1
                findings.append(f"  ⚠️  {path}")

        progress.finish()

        if findings:
            body = (
                f"  Scanned {checked} items\n"
                f"  {len(findings)} items to review:\n\n"
                + "\n".join(findings[:25])
                + "\n\n  Note: Not all flagged items are malware."
                "\n  Review manually before removing."
            )
        else:
            body = f"  Scanned {checked} locations.\n" "  No suspicious paths found ✅"

        show_result(
            "Malware Path Check",
            "Known malware location scan:",
            body,
        )

    threading.Thread(target=_worker, daemon=True).start()
