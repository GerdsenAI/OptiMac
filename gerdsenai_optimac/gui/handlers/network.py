"""
Network handler — DNS, connections, scanning, speed test.
"""

import threading

import rumps

from gerdsenai_optimac.gui.commands import run_command
from gerdsenai_optimac.gui.dialogs import show_result, StatusProgress
from gerdsenai_optimac.gui.sudo import run_privileged


def build_menu(app):
    """Build Network submenu."""
    menu = rumps.MenuItem("🌐 Network")

    menu.add(
        rumps.MenuItem(
            "Active Connections",
            callback=lambda _: active_connections(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Listening Ports",
            callback=lambda _: listening_ports(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Public IP",
            callback=lambda _: public_ip(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Ping Host",
            callback=lambda _: ping_host(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Speed Test",
            callback=lambda _: speed_test(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Wake-on-LAN",
            callback=lambda _: wake_on_lan(app),
        )
    )
    menu.add(rumps.separator)
    menu.add(
        rumps.MenuItem(
            "Flush DNS",
            callback=lambda _: flush_dns(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Flush Routes",
            callback=lambda _: flush_routes(app),
        )
    )
    menu.add(
        rumps.MenuItem(
            "Set DNS to Cloudflare",
            callback=lambda _: set_dns_cloudflare(app),
        )
    )
    return menu


# ── Tier 1 — Informational ────────────────────────────────────


def active_connections(app):
    progress = StatusProgress(app.status_item, "Network")
    progress.update("Scanning connections…")

    ok, out = run_command(
        ["lsof", "-i", "-P", "-n"],
        timeout=15,
    )
    progress.finish()

    if ok and out:
        lines = out.split("\n")
        # Filter to established connections
        established = [l for l in lines if "ESTABLISHED" in l or "COMMAND" in l]
        body = "\n".join(established[:30])
        count = len(established) - 1  # minus header
        show_result(
            "Active Connections",
            f"{count} established connection(s):",
            body,
        )
    else:
        show_result(
            "Active Connections",
            "Could not read connections",
            out or "lsof failed",
        )


def listening_ports(app):
    progress = StatusProgress(app.status_item, "Ports")
    progress.update("Scanning listening ports…")

    ok, out = run_command(
        ["lsof", "-i", "-P", "-n"],
        timeout=15,
    )
    progress.finish()

    if ok and out:
        lines = out.split("\n")
        listening = [l for l in lines if "LISTEN" in l or "COMMAND" in l]
        body = "\n".join(listening[:30])
        count = len(listening) - 1
        show_result(
            "Listening Ports",
            f"{count} service(s) listening:",
            body,
        )
    else:
        show_result(
            "Listening Ports",
            "Could not scan ports",
            out or "lsof failed",
        )


def public_ip(app):
    progress = StatusProgress(app.status_item, "IP")
    progress.update("Looking up public IP…")

    ok, ip = run_command(
        ["curl", "-s", "-m", "5", "ifconfig.me"],
    )
    progress.finish()

    if ok and ip:
        # Also get geolocation
        ok2, geo = run_command(
            ["curl", "-s", "-m", "5", f"https://ipinfo.io/{ip.strip()}/json"],
        )
        if ok2 and geo:
            import json

            try:
                data = json.loads(geo)
                loc = (
                    f"  IP:       {data.get('ip', ip.strip())}\n"
                    f"  City:     {data.get('city', '?')}\n"
                    f"  Region:   {data.get('region', '?')}\n"
                    f"  Country:  {data.get('country', '?')}\n"
                    f"  ISP:      {data.get('org', '?')}"
                )
                show_result("Public IP", "Your public IP:", loc)
                return
            except (json.JSONDecodeError, KeyError):
                pass
        show_result("Public IP", "Your public IP:", ip.strip())
    else:
        show_result(
            "Public IP",
            "Could not determine public IP",
            "Check your internet connection.",
        )


def ping_host(app):
    response = rumps.Window(
        "Enter hostname or IP to ping:",
        title="Ping Host",
        default_text="8.8.8.8",
        ok="Ping",
        cancel="Cancel",
    ).run()
    if not response.clicked:
        return
    host = response.text.strip()
    if not host:
        return

    progress = StatusProgress(app.status_item, "Ping")
    progress.update(f"Pinging {host}…")

    def _worker():
        ok, out = run_command(
            ["ping", "-c", "4", "-t", "5", host],
            timeout=25,
        )
        progress.finish()
        show_result(
            f"Ping {host}",
            "Ping results:" if ok else "Ping failed:",
            out or "No response",
        )

    threading.Thread(target=_worker, daemon=True).start()


def speed_test(app):
    progress = StatusProgress(app.status_item, "Speed Test")
    progress.update("Testing download speed…")

    def _worker():
        import time as _time

        # Download a 10MB test file from Cloudflare
        url = "https://speed.cloudflare.com/" "__down?measId=0&bytes=10000000"
        start = _time.time()
        ok, out = run_command(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{speed_download}", url],
            timeout=30,
        )
        elapsed = _time.time() - start

        progress.finish()

        if ok and out:
            try:
                bps = float(out)
                mbps = (bps * 8) / 1_000_000
                body = (
                    f"  Download:  {mbps:.1f} Mbps\n"
                    f"  Time:      {elapsed:.1f}s\n"
                    f"  Test size: 10 MB\n"
                    f"  Server:    Cloudflare"
                )
                show_result(
                    "Speed Test",
                    "Download speed:",
                    body,
                )
                return
            except ValueError:
                pass

        show_result(
            "Speed Test",
            "Speed test failed",
            out or "Could not connect to test server",
        )

    threading.Thread(target=_worker, daemon=True).start()


def wake_on_lan(app):
    response = rumps.Window(
        "Enter MAC address of target machine:\n" "(format: AA:BB:CC:DD:EE:FF)",
        title="Wake-on-LAN",
        default_text="",
        ok="Wake",
        cancel="Cancel",
    ).run()
    if not response.clicked:
        return
    mac = response.text.strip().upper()
    if not mac:
        return

    # Build and send magic packet
    try:
        import socket
        import struct

        mac_bytes = bytes.fromhex(mac.replace(":", ""))
        magic = b"\xff" * 6 + mac_bytes * 16

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as s:
            s.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_BROADCAST,
                1,
            )
            s.sendto(magic, ("255.255.255.255", 9))

        rumps.notification(
            "OptiMac",
            "WoL",
            f"Magic packet sent to {mac}",
        )
    except Exception as e:
        rumps.notification(
            "OptiMac",
            "WoL",
            f"Failed: {e}",
        )


# ── Tier 3 — Privileged ───────────────────────────────────────


def flush_dns(app):
    progress = StatusProgress(app.status_item, "DNS")
    progress.update("Requesting authorization…")
    ok, out = run_privileged("dscacheutil -flushcache && " "killall -HUP mDNSResponder")
    if ok:
        progress.finish("DNS flushed")
        rumps.notification("OptiMac", "DNS", "DNS cache flushed")
    else:
        progress.fail("DNS flush failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "DNS",
                f"Failed: {out}",
            )


def flush_routes(app):
    progress = StatusProgress(app.status_item, "Routes")
    progress.update("Requesting authorization…")
    ok, out = run_privileged("route -n flush")
    if ok:
        progress.finish("Routes flushed")
        rumps.notification(
            "OptiMac",
            "Routes",
            "Routing table flushed",
        )
    else:
        progress.fail("Route flush failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "Routes",
                f"Failed: {out}",
            )


def set_dns_cloudflare(app):
    # Detect the active network service name
    ok, iface = run_command(
        "networksetup -listallhardwareports"
        " | grep -A1 Wi-Fi | grep Device"
        " | awk '{print $2}'"
    )
    service = "Wi-Fi"
    if ok and iface.strip():
        ok2, svc = run_command(
            f"networksetup -listallhardwareports"
            f" | grep -B1 {iface.strip()}"
            f" | head -1"
            f" | sed 's/Hardware Port: //'"
        )
        if ok2 and svc.strip():
            service = svc.strip()

    progress = StatusProgress(app.status_item, "DNS")
    progress.update("Setting Cloudflare DNS…")

    ok, out = run_privileged(
        f"networksetup -setdnsservers " f"'{service}' 1.1.1.1 1.0.0.1"
    )
    if ok:
        progress.finish("DNS set")
        rumps.notification(
            "OptiMac",
            "DNS",
            f"Set to Cloudflare on {service}\n" f"1.1.1.1 · 1.0.0.1",
        )
    else:
        progress.fail("DNS change failed")
        if "Cancelled" not in out:
            rumps.notification(
                "OptiMac",
                "DNS",
                f"Failed: {out}",
            )
