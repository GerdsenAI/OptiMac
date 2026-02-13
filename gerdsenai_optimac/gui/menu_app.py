#!/usr/bin/env python3
"""
GerdsenAI OptiMac - macOS Menu Bar App

Runs in the macOS status bar (menu bar at top of screen) with the
GerdsenAI Neural G logo. Provides quick access to system monitoring,
AI stack management, optimization, and maintenance features.

Clicking the menu bar icon opens a dropdown with actions.
Dashboard and Settings open in separate tkinter windows.

Requires: rumps, psutil, Pillow (optional, for icon resize)
"""

import sys
import json
import threading
import subprocess
import time
from pathlib import Path

import psutil

try:
    import rumps
except ImportError:
    print("Error: 'rumps' is required. Install with: pip install rumps")
    sys.exit(1)

from gerdsenai_optimac.gui import (
    get_logo_path,
    generate_template_icon,
)
from gerdsenai_optimac.gui.monitors import (
    AppleSiliconMonitor,
    NetworkMonitor,
    get_compressed_memory_bytes,
)
from gerdsenai_optimac.gui.commands import run_command, run_command_threaded
from gerdsenai_optimac.gui.dialogs import (
    show_result,
    confirm_action,
    StatusProgress,
)
from gerdsenai_optimac.gui.sudo import run_privileged, run_privileged_batch


class OptiMacMenuBar(rumps.App):
    """macOS menu bar application for OptiMac."""

    def __init__(self):
        # Set up template icon (dark/light mode compatible)
        icon_path = self._setup_icon()

        super().__init__(
            name="OptiMac",
            icon=icon_path if icon_path else None,
            title=None if icon_path else "OptiMac",
            quit_button=None,  # We'll add our own
        )

        # Template images are black silhouettes with alpha.
        # macOS renders them white on dark bars, black on light.
        if icon_path:
            self.template = True

        # Set app icon so dialogs show the GerdsenAI logo
        # instead of the default Python rocket.
        self._set_app_icon()

        # Initialize monitors
        self.silicon_monitor = AppleSiliconMonitor()
        self.network_monitor = NetworkMonitor()
        self.config = self._load_config()

        # Status tracking
        self._monitoring = False
        self._monitor_thread = None

        # Build menu structure
        self._build_menu()

    def _setup_icon(self):
        """Generate a template icon (black silhouette with alpha)."""
        logo = get_logo_path()
        if logo:
            icon = generate_template_icon(logo, size=(22, 22))
            if icon:
                return icon
        return None

    def _set_app_icon(self):
        """Set the application icon to the GerdsenAI logo.

        When running from source (not a .app bundle), macOS shows
        the Python rocket icon in dialogs. This replaces it with
        the GerdsenAI Neural G so every alert, window, and
        notification feels branded.
        """
        try:
            from AppKit import NSApplication, NSImage

            logo = get_logo_path()
            if logo:
                img = NSImage.alloc().initWithContentsOfFile_(logo)
                if img:
                    NSApplication.sharedApplication().setApplicationIconImage_(img)
        except ImportError:
            pass  # pyobjc not available
        except Exception:
            pass  # non-critical — dialogs still work

    def _load_config(self):
        """Load OptiMac config from ~/.optimac/config.json."""
        config_file = Path.home() / ".optimac" / "config.json"
        try:
            if config_file.exists():
                with open(config_file) as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save_config(self, config):
        """Save config to disk."""
        config_dir = Path.home() / ".optimac"
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)
        self.config = config

    def _build_menu(self):
        """Build the dropdown menu structure."""
        chip = self.silicon_monitor.chip_info
        mem = psutil.virtual_memory()
        mem_gb = mem.total / (1024**3)

        # System info header (non-clickable)
        self.menu.add(
            rumps.MenuItem(
                f"Apple {chip['model']} | {mem_gb:.0f}GB"
                f" | {chip['cpu_cores']} CPU"
                f" | {chip['gpu_cores']} GPU",
                callback=None,
            )
        )
        self.menu.add(rumps.separator)

        # Quick status
        self.status_item = rumps.MenuItem("Status: Ready")
        self.menu.add(self.status_item)
        self.menu.add(rumps.separator)

        # AI Stack submenu
        ai_menu = rumps.MenuItem("AI Stack")
        ai_menu.add(
            rumps.MenuItem(
                "Start Ollama",
                callback=self._start_ollama,
            )
        )
        ai_menu.add(
            rumps.MenuItem(
                "Stop Ollama",
                callback=self._stop_ollama,
            )
        )
        ai_menu.add(rumps.separator)
        ai_menu.add(
            rumps.MenuItem(
                "Start MLX Server",
                callback=self._start_mlx,
            )
        )
        ai_menu.add(
            rumps.MenuItem(
                "Stop MLX Server",
                callback=self._stop_mlx,
            )
        )
        ai_menu.add(rumps.separator)
        ai_menu.add(
            rumps.MenuItem(
                "Check Status",
                callback=self._check_ai_status,
            )
        )
        ai_menu.add(
            rumps.MenuItem(
                "List Models",
                callback=self._list_models,
            )
        )
        self.menu.add(ai_menu)

        # Edge Endpoints submenu
        edge_menu = rumps.MenuItem("Edge Endpoints")
        edge_menu.add(
            rumps.MenuItem(
                "List Endpoints",
                callback=self._list_edge_endpoints,
            )
        )
        edge_menu.add(
            rumps.MenuItem(
                "Test All Endpoints",
                callback=self._test_edge_endpoints,
            )
        )
        self.menu.add(edge_menu)

        # Quick Actions submenu
        actions_menu = rumps.MenuItem("Quick Actions")
        actions_menu.add(
            rumps.MenuItem(
                "Check Memory Pressure",
                callback=self._check_memory,
            )
        )
        actions_menu.add(
            rumps.MenuItem(
                "Purge Memory",
                callback=self._purge_memory,
            )
        )
        actions_menu.add(rumps.separator)
        actions_menu.add(
            rumps.MenuItem(
                "Flush DNS",
                callback=self._flush_dns,
            )
        )
        actions_menu.add(
            rumps.MenuItem(
                "Flush Routes",
                callback=self._flush_routes,
            )
        )
        actions_menu.add(rumps.separator)
        actions_menu.add(
            rumps.MenuItem(
                "Clear Caches",
                callback=self._clear_caches,
            )
        )
        actions_menu.add(
            rumps.MenuItem(
                "Run Full Maintenance",
                callback=self._run_maintenance,
            )
        )
        self.menu.add(actions_menu)

        # Optimize submenu
        optimize_menu = rumps.MenuItem("Optimize")
        optimize_menu.add(
            rumps.MenuItem(
                "Apply Power Profile",
                callback=self._apply_power,
            )
        )
        optimize_menu.add(
            rumps.MenuItem(
                "Reduce UI Overhead",
                callback=self._reduce_ui,
            )
        )
        optimize_menu.add(
            rumps.MenuItem(
                "Set DNS to Cloudflare",
                callback=self._set_dns_cloudflare,
            )
        )
        self.menu.add(optimize_menu)

        self.menu.add(rumps.separator)

        # Toggle monitoring
        self.monitor_toggle = rumps.MenuItem(
            "Start Monitoring", callback=self._toggle_monitoring
        )
        self.menu.add(self.monitor_toggle)

        # Utility
        self.menu.add(
            rumps.MenuItem(
                "Open Config File",
                callback=self._open_config,
            )
        )
        self.menu.add(
            rumps.MenuItem(
                "View in Terminal",
                callback=self._open_terminal,
            )
        )

        self.menu.add(rumps.separator)
        self.menu.add(
            rumps.MenuItem(
                "Quit OptiMac",
                callback=self._quit,
            )
        )

    # ════════════════════════════════════════════════════════════
    #  Tier 2 — Safe Actions (notification + status update)
    # ════════════════════════════════════════════════════════════

    def _start_ollama(self, _):
        progress = StatusProgress(self.status_item, "Ollama")
        progress.update("Starting server…")

        def _cb(ok, out):
            if ok:
                progress.finish("Ollama running")
                rumps.notification(
                    "OptiMac",
                    "Ollama",
                    "Server started",
                )
            else:
                progress.fail("Ollama failed")
                rumps.notification(
                    "OptiMac",
                    "Ollama",
                    f"Failed: {out}",
                )

        run_command_threaded(
            ["ollama", "serve"],
            callback=_cb,
            timeout=10,
        )

    def _stop_ollama(self, _):
        progress = StatusProgress(self.status_item, "Ollama")
        progress.update("Stopping…")
        ok, out = run_command(["pkill", "-f", "ollama serve"])
        if ok:
            progress.finish("Ollama stopped")
        else:
            progress.finish("Ollama was not running")
        rumps.notification(
            "OptiMac",
            "Ollama",
            "Server stopped" if ok else "Not running",
        )

    def _start_mlx(self, _):
        response = rumps.Window(
            "Enter HuggingFace model ID or local path:",
            title="Start MLX Server",
            default_text="mlx-community/Qwen2.5-7B-Instruct-4bit",
            ok="Start",
            cancel="Cancel",
        ).run()
        if response.clicked:
            model = response.text.strip()
            if model:
                port = self.config.get(
                    "aiStackPorts",
                    {},
                ).get("mlx", 8080)
                progress = StatusProgress(
                    self.status_item,
                    "MLX",
                )
                progress.update(f"Starting on port {port}…")
                subprocess.Popen(
                    [
                        "python3",
                        "-m",
                        "mlx_lm.server",
                        "--model",
                        model,
                        "--port",
                        str(port),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                progress.finish(f"MLX on :{port}")
                rumps.notification(
                    "OptiMac",
                    "MLX",
                    f"Starting server with {model}\n" f"Port {port}",
                )

    def _stop_mlx(self, _):
        progress = StatusProgress(self.status_item, "MLX")
        progress.update("Stopping…")
        run_command(["pkill", "-f", "mlx_lm.server"])
        progress.finish("MLX stopped")
        rumps.notification("OptiMac", "MLX", "Server stopped")

    # ════════════════════════════════════════════════════════════
    #  Tier 1 — Informational (persistent result panels)
    # ════════════════════════════════════════════════════════════

    def _check_ai_status(self, _):
        import socket

        ports = self.config.get(
            "aiStackPorts",
            {
                "ollama": 11434,
                "lmstudio": 1234,
                "mlx": 8080,
            },
        )
        lines = []
        for name, port in ports.items():
            try:
                with socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                ) as s:
                    s.settimeout(1)
                    running = (
                        s.connect_ex(
                            ("127.0.0.1", port),
                        )
                        == 0
                    )
            except OSError:
                running = False
            icon = "● RUNNING" if running else "○ stopped"
            lines.append(f"  {name:<12} {icon}  (:{port})")

        show_result(
            "AI Stack Status",
            "Local inference services:",
            "\n".join(lines) if lines else "No services configured",
        )

    def _list_models(self, _):
        progress = StatusProgress(self.status_item, "Models")
        progress.update("Querying Ollama…")
        ok, out = run_command(["ollama", "list"], timeout=10)
        progress.finish()

        if ok and out:
            show_result("Ollama Models", "Installed models:", out)
        else:
            show_result(
                "Ollama Models",
                "No models found",
                "Ollama may not be running.\n" "Start it from AI Stack → Start Ollama.",
            )

    def _list_edge_endpoints(self, _):
        endpoints = self.config.get("edgeEndpoints", {})
        if not endpoints:
            show_result(
                "Edge Endpoints",
                "No edge endpoints configured.",
                "Register one with the MCP tool:\n" "  optimac_edge_add",
            )
            return
        lines = []
        for name, ep in endpoints.items():
            url = ep.get("url", "?")
            rt = ep.get("runtimeType", "?")
            lines.append(f"  {name:<16} {url}  ({rt})")
        show_result(
            f"Edge Endpoints ({len(endpoints)})",
            "Registered endpoints:",
            "\n".join(lines),
        )

    def _test_edge_endpoints(self, _):
        import socket

        endpoints = self.config.get("edgeEndpoints", {})
        if not endpoints:
            show_result(
                "Edge Endpoints",
                "No endpoints configured.",
                "Register one with the MCP tool:\n" "  optimac_edge_add",
            )
            return

        progress = StatusProgress(
            self.status_item,
            "Endpoint Test",
        )
        results = []
        total = len(endpoints)
        for i, (name, ep) in enumerate(endpoints.items()):
            progress.update(
                f"Testing {name}…",
                step=i + 1,
                total=total,
            )
            url = ep.get("url", "")
            try:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 80
                with socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                ) as s:
                    s.settimeout(2)
                    reachable = (
                        s.connect_ex(
                            (host, port),
                        )
                        == 0
                    )
                status = "● OK" if reachable else "✗ UNREACHABLE"
            except Exception:
                status = "✗ ERROR"
            results.append(f"  {name:<16} {status}")
        progress.finish("Tests complete")

        show_result(
            "Endpoint Test Results",
            f"Tested {total} endpoint(s):",
            "\n".join(results),
        )

    # ════════════════════════════════════════════════════════════
    #  Tier 1 — Informational (memory)
    # ════════════════════════════════════════════════════════════

    def _check_memory(self, _):
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

        body = (
            f"  Pressure:    {pressure}\n"
            f"  Used:        {used_gb:.1f} GB / {total_gb:.1f} GB"
            f" ({pct:.0f}%)\n"
            f"  Compressed:  {compressed_gb:.1f} GB\n"
            f"  Available:   {avail_gb:.1f} GB"
        )
        show_result("Memory Pressure", "Current memory state:", body)

    # ════════════════════════════════════════════════════════════
    #  Tier 3 — Privileged (password prompt → progress → result)
    # ════════════════════════════════════════════════════════════

    def _purge_memory(self, _):
        progress = StatusProgress(self.status_item, "Purge")
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

    def _flush_dns(self, _):
        progress = StatusProgress(self.status_item, "DNS")
        progress.update("Requesting authorization…")
        ok, out = run_privileged(
            "dscacheutil -flushcache && " "killall -HUP mDNSResponder"
        )
        if ok:
            progress.finish("DNS flushed")
            rumps.notification(
                "OptiMac",
                "DNS",
                "DNS cache flushed",
            )
        else:
            progress.fail("DNS flush failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "DNS",
                    f"Failed: {out}",
                )

    def _flush_routes(self, _):
        progress = StatusProgress(self.status_item, "Routes")
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

    # ════════════════════════════════════════════════════════════
    #  Tier 4 — Destructive (confirm → password → progress)
    # ════════════════════════════════════════════════════════════

    def _clear_caches(self, _):
        # Estimate cache size for the confirmation dialog
        cache_dir = Path.home() / "Library" / "Caches"
        try:
            ok, size_out = run_command(
                ["du", "-sh", str(cache_dir)],
                timeout=10,
            )
            size_str = size_out.split()[0] if ok else "unknown"
        except Exception:
            size_str = "unknown"

        proceed = confirm_action(
            "Clear Application Caches",
            f"This will remove cached data from:\n\n"
            f"  ~/Library/Caches  ({size_str})\n\n"
            f"Applications may run slower until they\n"
            f"rebuild their caches.\n\n"
            f"This cannot be undone.",
            proceed_label="Clear Caches",
        )
        if not proceed:
            return

        progress = StatusProgress(self.status_item, "Caches")
        progress.update("Clearing caches…")

        # Safer approach: clear contents, not the directory itself
        cmd = f"find {cache_dir} -mindepth 1 -maxdepth 1 " f"-exec rm -rf {{}} +"
        ok, out = run_privileged(cmd)

        if ok:
            progress.finish("Caches cleared")
            rumps.notification(
                "OptiMac",
                "Caches",
                "Application caches cleared",
            )
        else:
            progress.fail("Cache clear failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "Caches",
                    f"Failed: {out}",
                )

    def _run_maintenance(self, _):
        proceed = confirm_action(
            "Run Full Maintenance",
            "This will run the following operations:\n\n"
            "  1. Purge inactive memory\n"
            "  2. Flush DNS cache\n"
            "  3. Flush routing table\n\n"
            "Administrator password required.",
            proceed_label="Run Maintenance",
        )
        if not proceed:
            return

        def _worker():
            progress = StatusProgress(
                self.status_item,
                "Maintenance",
            )
            steps = [
                ("Purging memory", "purge"),
                (
                    "Flushing DNS",
                    ("dscacheutil -flushcache && " "killall -HUP mDNSResponder"),
                ),
                ("Flushing routes", "route -n flush"),
            ]

            ok, results = run_privileged_batch(
                steps,
                progress_callback=lambda s, t, d: (progress.update(d, step=s, total=t)),
            )

            if ok:
                progress.finish("Maintenance complete")
                rumps.notification(
                    "OptiMac",
                    "Maintenance",
                    "Full maintenance cycle complete\n"
                    "Memory purged · DNS flushed · "
                    "Routes flushed",
                )
            else:
                progress.fail("Maintenance failed")
                err_msg = results[0][1] if results else "Unknown"
                if "Cancelled" not in err_msg:
                    rumps.notification(
                        "OptiMac",
                        "Maintenance",
                        f"Failed: {err_msg}",
                    )

        threading.Thread(target=_worker, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    #  Tier 3 — Privileged Optimize Actions
    # ════════════════════════════════════════════════════════════

    def _apply_power(self, _):
        progress = StatusProgress(
            self.status_item,
            "Power Profile",
        )
        progress.update("Applying settings…")

        cmd = (
            "pmset -a sleep 0 && "
            "pmset -a displaysleep 0 && "
            "pmset -a disksleep 0 && "
            "pmset -a womp 1 && "
            "pmset -a autorestart 1 && "
            "pmset -a powernap 0"
        )
        ok, out = run_privileged(cmd)

        if ok:
            progress.finish("Power profile applied")
            rumps.notification(
                "OptiMac",
                "Power",
                "AI inference power profile applied\n"
                "Sleep disabled · Wake-on-LAN on · "
                "Auto-restart on",
            )
        else:
            progress.fail("Power profile failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "Power",
                    f"Failed: {out}",
                )

    def _reduce_ui(self, _):
        """Reduce UI overhead — no sudo needed for defaults write."""
        progress = StatusProgress(
            self.status_item,
            "UI Optimization",
        )
        progress.update("Reducing visual effects…")

        commands = [
            [
                "defaults",
                "write",
                "com.apple.universalaccess",
                "reduceMotion",
                "-bool",
                "true",
            ],
            [
                "defaults",
                "write",
                "com.apple.universalaccess",
                "reduceTransparency",
                "-bool",
                "true",
            ],
            [
                "defaults",
                "write",
                "NSGlobalDomain",
                "NSAutomaticWindowAnimationsEnabled",
                "-bool",
                "false",
            ],
            [
                "defaults",
                "write",
                "com.apple.dock",
                "autohide-time-modifier",
                "-float",
                "0",
            ],
            [
                "defaults",
                "write",
                "com.apple.dock",
                "expose-animation-duration",
                "-float",
                "0.1",
            ],
        ]
        for cmd in commands:
            run_command(cmd)
        run_command(["killall", "Dock"])

        progress.finish("UI optimized")
        rumps.notification(
            "OptiMac",
            "UI",
            "Visual effects reduced\n" "Motion · Transparency · Animations",
        )

    def _set_dns_cloudflare(self, _):
        # Detect the active network service name
        ok, iface = run_command(
            "networksetup -listallhardwareports"
            " | grep -A1 Wi-Fi | grep Device"
            " | awk '{print $2}'"
        )
        # Use detected service name, fall back to Wi-Fi
        service = "Wi-Fi"
        if ok and iface.strip():
            # Verify the detected interface has a service name
            ok2, svc = run_command(
                f"networksetup -listallhardwareports"
                f" | grep -B1 {iface.strip()}"
                f" | head -1"
                f" | sed 's/Hardware Port: //'"
            )
            if ok2 and svc.strip():
                service = svc.strip()

        progress = StatusProgress(self.status_item, "DNS")
        progress.update("Setting Cloudflare DNS…")

        ok, out = run_privileged(
            f"networksetup -setdnsservers " f"'{service}' 1.1.1.1 1.0.0.1"
        )
        if ok:
            progress.finish("DNS set")
            rumps.notification(
                "OptiMac",
                "DNS",
                f"Set to Cloudflare on {service}\n"
                f"Primary: 1.1.1.1 · Secondary: 1.0.0.1",
            )
        else:
            progress.fail("DNS change failed")
            if "Cancelled" not in out:
                rumps.notification(
                    "OptiMac",
                    "DNS",
                    f"Failed: {out}",
                )

    # ════════════════════════════════════════════════════════════
    #  Monitoring
    # ════════════════════════════════════════════════════════════

    def _toggle_monitoring(self, sender):
        if self._monitoring:
            self._monitoring = False
            sender.title = "Start Monitoring"
            self.status_item.title = "Status: Ready"
        else:
            self._monitoring = True
            sender.title = "Stop Monitoring"
            self._start_monitor_loop()

    def _start_monitor_loop(self):
        def _loop():
            while self._monitoring:
                try:
                    mem = psutil.virtual_memory()
                    cpu = psutil.cpu_percent(interval=1)
                    pct = mem.percent
                    if pct < 75:
                        pressure = "OK"
                    elif pct < 90:
                        pressure = "WARN"
                    else:
                        pressure = "CRIT"
                    self.status_item.title = (
                        f"CPU: {cpu:.0f}%" f" | RAM: {pct:.0f}% ({pressure})"
                    )
                except Exception:
                    self.status_item.title = "Status: Error"
                time.sleep(2)

        t = threading.Thread(target=_loop, daemon=True)
        self._monitor_thread = t
        t.start()

    # ════════════════════════════════════════════════════════════
    #  Utility
    # ════════════════════════════════════════════════════════════

    def _open_config(self, _):
        config_file = Path.home() / ".optimac" / "config.json"
        if config_file.exists():
            subprocess.Popen(["open", str(config_file)])
        else:
            show_result(
                "Configuration",
                "No config file found.",
                "Expected location:\n"
                "  ~/.optimac/config.json\n\n"
                "A config file is created automatically\n"
                "when you use MCP tools.",
            )

    def _open_terminal(self, _):
        """Open the legacy tkinter GUI in a terminal."""
        script_dir = Path(__file__).parent.parent.parent
        legacy = script_dir / "gerdsenai_optimac_improved.py"
        if legacy.exists():
            subprocess.Popen(["python3", str(legacy)])
        else:
            show_result(
                "Terminal GUI",
                "Legacy GUI not found.",
                f"Expected at:\n  {legacy}",
            )

    def _quit(self, _):
        rumps.quit_application()


def main():
    """Entry point for the menu bar app."""
    import platform

    if platform.system() != "Darwin":
        print("Error: OptiMac requires macOS")
        sys.exit(1)

    app = OptiMacMenuBar()
    app.run()


if __name__ == "__main__":
    main()
