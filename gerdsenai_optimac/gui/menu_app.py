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
import os
import json
import threading
import subprocess
import time
from pathlib import Path
from datetime import datetime

import psutil

try:
    import rumps
except ImportError:
    print("Error: 'rumps' is required. Install with: pip install rumps")
    sys.exit(1)

from gerdsenai_optimac.gui import get_logo_path, generate_menu_icon
from gerdsenai_optimac.gui.monitors import (
    AppleSiliconMonitor,
    NetworkMonitor,
    get_compressed_memory_bytes,
)
from gerdsenai_optimac.gui.commands import run_command, run_command_threaded


class OptiMacMenuBar(rumps.App):
    """macOS menu bar application for OptiMac."""

    def __init__(self):
        # Set up icon
        icon_path = self._setup_icon()

        super().__init__(
            name="OptiMac",
            icon=icon_path if icon_path else None,
            title=None if icon_path else "OptiMac",
            quit_button=None,  # We'll add our own
        )

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
        """Find and resize logo for menu bar."""
        logo = get_logo_path()
        if logo:
            icon = generate_menu_icon(logo, size=(22, 22))
            if icon:
                return icon
        return None

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
        mem_gb = mem.total / (1024 ** 3)

        # System info header (non-clickable)
        self.menu.add(rumps.MenuItem(
            f"Apple {chip['model']} | {mem_gb:.0f}GB | {chip['cpu_cores']} CPU | {chip['gpu_cores']} GPU",
            callback=None,
        ))
        self.menu.add(rumps.separator)

        # Quick status
        self.status_item = rumps.MenuItem("Status: Ready")
        self.menu.add(self.status_item)
        self.menu.add(rumps.separator)

        # AI Stack submenu
        ai_menu = rumps.MenuItem("AI Stack")
        ai_menu.add(rumps.MenuItem("Start Ollama", callback=self._start_ollama))
        ai_menu.add(rumps.MenuItem("Stop Ollama", callback=self._stop_ollama))
        ai_menu.add(rumps.separator)
        ai_menu.add(rumps.MenuItem("Start MLX Server", callback=self._start_mlx))
        ai_menu.add(rumps.MenuItem("Stop MLX Server", callback=self._stop_mlx))
        ai_menu.add(rumps.separator)
        ai_menu.add(rumps.MenuItem("Check Status", callback=self._check_ai_status))
        ai_menu.add(rumps.MenuItem("List Models", callback=self._list_models))
        self.menu.add(ai_menu)

        # Edge Endpoints submenu
        edge_menu = rumps.MenuItem("Edge Endpoints")
        edge_menu.add(rumps.MenuItem("List Endpoints", callback=self._list_edge_endpoints))
        edge_menu.add(rumps.MenuItem("Test All Endpoints", callback=self._test_edge_endpoints))
        self.menu.add(edge_menu)

        # Quick Actions submenu
        actions_menu = rumps.MenuItem("Quick Actions")
        actions_menu.add(rumps.MenuItem("Check Memory Pressure", callback=self._check_memory))
        actions_menu.add(rumps.MenuItem("Purge Memory", callback=self._purge_memory))
        actions_menu.add(rumps.separator)
        actions_menu.add(rumps.MenuItem("Flush DNS", callback=self._flush_dns))
        actions_menu.add(rumps.MenuItem("Flush Routes", callback=self._flush_routes))
        actions_menu.add(rumps.separator)
        actions_menu.add(rumps.MenuItem("Clear Caches", callback=self._clear_caches))
        actions_menu.add(rumps.MenuItem("Run Full Maintenance", callback=self._run_maintenance))
        self.menu.add(actions_menu)

        # Optimize submenu
        optimize_menu = rumps.MenuItem("Optimize")
        optimize_menu.add(rumps.MenuItem("Apply Power Profile", callback=self._apply_power))
        optimize_menu.add(rumps.MenuItem("Reduce UI Overhead", callback=self._reduce_ui))
        optimize_menu.add(rumps.MenuItem("Set DNS to Cloudflare", callback=self._set_dns_cloudflare))
        self.menu.add(optimize_menu)

        self.menu.add(rumps.separator)

        # Toggle monitoring
        self.monitor_toggle = rumps.MenuItem(
            "Start Monitoring", callback=self._toggle_monitoring
        )
        self.menu.add(self.monitor_toggle)

        # Open config
        self.menu.add(rumps.MenuItem("Open Config File", callback=self._open_config))
        self.menu.add(rumps.MenuItem("View in Terminal", callback=self._open_terminal))

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit OptiMac", callback=self._quit))

    # ---- AI Stack Actions ----

    def _start_ollama(self, _):
        def _cb(ok, out):
            rumps.notification("OptiMac", "Ollama", "Server started" if ok else f"Failed: {out}")
        run_command_threaded(["ollama", "serve"], callback=_cb, timeout=10)
        rumps.notification("OptiMac", "Ollama", "Starting Ollama server...")

    def _stop_ollama(self, _):
        ok, out = run_command(["pkill", "-f", "ollama serve"])
        rumps.notification("OptiMac", "Ollama", "Server stopped" if ok else "Not running")

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
                port = self.config.get("aiStackPorts", {}).get("mlx", 8080)
                subprocess.Popen(
                    ["python3", "-m", "mlx_lm.server", "--model", model, "--port", str(port)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                rumps.notification("OptiMac", "MLX", f"Starting server with {model} on port {port}")

    def _stop_mlx(self, _):
        run_command(["pkill", "-f", "mlx_lm.server"])
        rumps.notification("OptiMac", "MLX", "Server stopped")

    def _check_ai_status(self, _):
        import socket
        ports = self.config.get("aiStackPorts", {"ollama": 11434, "lmstudio": 1234, "mlx": 8080})
        status_lines = []
        for name, port in ports.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    running = s.connect_ex(("127.0.0.1", port)) == 0
            except OSError:
                running = False
            icon = "ON" if running else "OFF"
            status_lines.append(f"  {name}: {icon} (port {port})")
        rumps.notification("OptiMac", "AI Stack Status", "\n".join(status_lines))

    def _list_models(self, _):
        ok, out = run_command(["ollama", "list"], timeout=10)
        if ok and out:
            # Truncate for notification
            lines = out.split("\n")[:6]
            rumps.notification("OptiMac", "Ollama Models", "\n".join(lines))
        else:
            rumps.notification("OptiMac", "Models", "No models found or Ollama not running")

    # ---- Edge Endpoint Actions ----

    def _list_edge_endpoints(self, _):
        endpoints = self.config.get("edgeEndpoints", {})
        if not endpoints:
            rumps.notification("OptiMac", "Edge Endpoints", "No edge endpoints configured.\nUse MCP tool optimac_edge_add to register one.")
            return
        lines = []
        for name, ep in endpoints.items():
            lines.append(f"  {name}: {ep.get('url', '?')} ({ep.get('runtimeType', '?')})")
        rumps.notification("OptiMac", f"Edge Endpoints ({len(endpoints)})", "\n".join(lines[:8]))

    def _test_edge_endpoints(self, _):
        import socket
        endpoints = self.config.get("edgeEndpoints", {})
        if not endpoints:
            rumps.notification("OptiMac", "Edge", "No endpoints configured")
            return
        results = []
        for name, ep in endpoints.items():
            url = ep.get("url", "")
            try:
                # Extract host:port from URL
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 80
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    reachable = s.connect_ex((host, port)) == 0
                results.append(f"  {name}: {'OK' if reachable else 'UNREACHABLE'}")
            except Exception:
                results.append(f"  {name}: ERROR")
        rumps.notification("OptiMac", "Edge Test", "\n".join(results[:8]))

    # ---- Quick Actions ----

    def _check_memory(self, _):
        mem = psutil.virtual_memory()
        compressed = get_compressed_memory_bytes()
        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        compressed_gb = compressed / (1024 ** 3)
        pct = mem.percent
        pressure = "NOMINAL" if pct < 75 else ("WARNING" if pct < 90 else "CRITICAL")
        msg = (
            f"Pressure: {pressure}\n"
            f"Used: {used_gb:.1f}GB / {total_gb:.1f}GB ({pct:.0f}%)\n"
            f"Compressed: {compressed_gb:.1f}GB\n"
            f"Available: {mem.available / (1024**3):.1f}GB"
        )
        rumps.notification("OptiMac", "Memory Pressure", msg)

    def _purge_memory(self, _):
        def _cb(ok, out):
            rumps.notification("OptiMac", "Purge", "Memory purged" if ok else f"Failed (need sudo): {out}")
        run_command_threaded(["sudo", "purge"], callback=_cb)

    def _flush_dns(self, _):
        run_command(["sudo", "dscacheutil", "-flushcache"])
        run_command(["sudo", "killall", "-HUP", "mDNSResponder"])
        rumps.notification("OptiMac", "DNS", "DNS cache flushed")

    def _flush_routes(self, _):
        ok, out = run_command(["sudo", "route", "-n", "flush"])
        rumps.notification("OptiMac", "Routes", "Routing table flushed" if ok else f"Failed: {out}")

    def _clear_caches(self, _):
        cleared = 0
        for path in ["/tmp", str(Path.home() / "Library" / "Caches")]:
            try:
                ok, _ = run_command(["sudo", "rm", "-rf", f"{path}/*"])
                if ok:
                    cleared += 1
            except Exception:
                pass
        rumps.notification("OptiMac", "Caches", f"Cleared {cleared} cache locations")

    def _run_maintenance(self, _):
        def _worker():
            steps = [
                ("Purging memory...", ["sudo", "purge"]),
                ("Flushing DNS...", ["sudo", "dscacheutil", "-flushcache"]),
                ("Flushing routes...", ["sudo", "route", "-n", "flush"]),
            ]
            for desc, cmd in steps:
                run_command(cmd)
            rumps.notification("OptiMac", "Maintenance", "Full maintenance cycle complete")

        threading.Thread(target=_worker, daemon=True).start()
        rumps.notification("OptiMac", "Maintenance", "Running maintenance cycle...")

    # ---- Optimize Actions ----

    def _apply_power(self, _):
        commands = [
            ["sudo", "pmset", "-a", "sleep", "0"],
            ["sudo", "pmset", "-a", "displaysleep", "0"],
            ["sudo", "pmset", "-a", "disksleep", "0"],
            ["sudo", "pmset", "-a", "womp", "1"],
            ["sudo", "pmset", "-a", "autorestart", "1"],
            ["sudo", "pmset", "-a", "powernap", "0"],
        ]
        for cmd in commands:
            run_command(cmd)
        rumps.notification("OptiMac", "Power", "AI inference power profile applied")

    def _reduce_ui(self, _):
        commands = [
            ["defaults", "write", "com.apple.universalaccess", "reduceMotion", "-bool", "true"],
            ["defaults", "write", "com.apple.universalaccess", "reduceTransparency", "-bool", "true"],
            ["defaults", "write", "NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "-bool", "false"],
            ["defaults", "write", "com.apple.dock", "autohide-time-modifier", "-float", "0"],
            ["defaults", "write", "com.apple.dock", "expose-animation-duration", "-float", "0.1"],
        ]
        for cmd in commands:
            run_command(cmd)
        run_command(["killall", "Dock"])
        rumps.notification("OptiMac", "UI", "Visual effects reduced for inference performance")

    def _set_dns_cloudflare(self, _):
        ok, iface = run_command(
            "networksetup -listallhardwareports | grep -A1 Wi-Fi | grep Device | awk '{print $2}'"
        )
        interface = iface.strip() if ok and iface.strip() else "en0"
        run_command(["sudo", "networksetup", "-setdnsservers", f"Wi-Fi", "1.1.1.1", "1.0.0.1"])
        rumps.notification("OptiMac", "DNS", "Set to Cloudflare (1.1.1.1, 1.0.0.1)")

    # ---- Monitoring ----

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
                    pressure = "OK" if pct < 75 else ("WARN" if pct < 90 else "CRIT")
                    self.status_item.title = f"CPU: {cpu:.0f}% | RAM: {pct:.0f}% ({pressure})"
                except Exception:
                    self.status_item.title = "Status: Error"
                time.sleep(2)

        self._monitor_thread = threading.Thread(target=_loop, daemon=True)
        self._monitor_thread.start()

    # ---- Utility ----

    def _open_config(self, _):
        config_file = Path.home() / ".optimac" / "config.json"
        if config_file.exists():
            subprocess.Popen(["open", str(config_file)])
        else:
            rumps.notification("OptiMac", "Config", "No config file found at ~/.optimac/config.json")

    def _open_terminal(self, _):
        """Open the legacy tkinter GUI in a terminal."""
        script_dir = Path(__file__).parent.parent.parent
        legacy = script_dir / "gerdsenai_optimac_improved.py"
        if legacy.exists():
            subprocess.Popen(["python3", str(legacy)])
        else:
            rumps.notification("OptiMac", "Terminal", "Legacy GUI not found")

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
