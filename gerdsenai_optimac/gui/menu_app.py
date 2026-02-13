#!/usr/bin/env python3
"""
GerdsenAI OptiMac - macOS Menu Bar App

Runs in the macOS status bar with the GerdsenAI Neural G logo.
Provides quick access to system monitoring, AI stack management,
security auditing, network tools, and optimization features.

Clicking the menu bar icon opens a dropdown with 60+ actions
organized into themed submenus, powered by handler modules.

Requires: rumps, psutil, Pillow (optional, for icon resize)
"""

import sys
import json
import threading
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
)
from gerdsenai_optimac.gui.dialogs import show_result, set_terminal_widget
from gerdsenai_optimac.gui.icons import get_icon
from gerdsenai_optimac.gui.terminal_widget import TerminalWidget

# Handler modules — each provides build_menu(app) -> MenuItem
from gerdsenai_optimac.gui.handlers import (
    ai_stack,
    system,
    performance,
    network,
    security,
    optimize,
)


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

        # Terminal widget (floating mini-terminal)
        self.terminal = TerminalWidget()
        set_terminal_widget(self.terminal)

        # Build menu structure
        self._build_menu()

        # Sync toggle text when panel is closed via ✕
        self.terminal.set_on_close(self._on_terminal_closed)

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

    # ══════════════════════════════════════════════════════════
    #  Menu Structure
    # ══════════════════════════════════════════════════════════

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

        # ── Feature submenus (from handler modules) ──
        self.menu.add(ai_stack.build_menu(self))
        self.menu.add(system.build_menu(self))
        self.menu.add(performance.build_menu(self))
        self.menu.add(network.build_menu(self))
        self.menu.add(security.build_menu(self))
        self.menu.add(optimize.build_menu(self))

        # Edge Endpoints (from config)
        edge_menu = rumps.MenuItem(
            "Edge Endpoints", icon=get_icon("radio"), dimensions=(16, 16), template=True
        )
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

        self.menu.add(rumps.separator)

        # Toggle monitoring
        self.monitor_toggle = rumps.MenuItem(
            "Start Monitoring", callback=self._toggle_monitoring
        )
        self.menu.add(self.monitor_toggle)

        # Utility
        self.terminal_toggle = rumps.MenuItem(
            "Show Terminal",
            callback=self._toggle_terminal,
            icon=get_icon("terminal"),
            dimensions=(16, 16),
            template=True,
        )
        self.menu.add(self.terminal_toggle)
        self.menu.add(
            rumps.MenuItem(
                "Open Config File",
                callback=self._open_config,
            )
        )

        self.menu.add(rumps.separator)
        self.menu.add(
            rumps.MenuItem(
                "Quit OptiMac",
                callback=self._quit,
            )
        )

    # ══════════════════════════════════════════════════════════
    #  Edge Endpoints (config-driven)
    # ══════════════════════════════════════════════════════════

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
        for name, info in endpoints.items():
            url = info.get("url", "?")
            status = info.get("status", "unknown")
            lines.append(f"  {name:<16} {url}\n" f"  {'':16} status: {status}")
        show_result(
            "Edge Endpoints",
            f"{len(endpoints)} endpoint(s):",
            "\n".join(lines),
        )

    def _test_edge_endpoints(self, _):
        import socket

        endpoints = self.config.get("edgeEndpoints", {})
        if not endpoints:
            show_result(
                "Edge Endpoints",
                "No edge endpoints configured.",
                "Register one first.",
            )
            return

        lines = []
        for name, info in endpoints.items():
            url = info.get("url", "")
            try:
                host = url.split("://")[-1].split(":")[0]
                port = int(url.split(":")[-1].split("/")[0])
                with socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                ) as s:
                    s.settimeout(3)
                    reachable = (
                        s.connect_ex(
                            (host, port),
                        )
                        == 0
                    )
                icon = "[OK]" if reachable else "[DOWN]"
            except Exception:
                icon = "[ERR]"
            lines.append(f"  {name:<16} {icon}")

        show_result(
            "Endpoint Tests",
            f"Tested {len(endpoints)} endpoint(s):",
            "\n".join(lines),
        )

    # ══════════════════════════════════════════════════════════
    #  Monitoring
    # ══════════════════════════════════════════════════════════

    def _toggle_monitoring(self, sender):
        if self._monitoring:
            self._monitoring = False
            sender.title = "Start Monitoring"
            self.title = None
            rumps.notification(
                "OptiMac",
                "Monitoring",
                "Monitoring stopped",
            )
        else:
            self._monitoring = True
            sender.title = "Stop Monitoring"

            def _monitor():
                while self._monitoring:
                    cpu = psutil.cpu_percent(interval=2)
                    mem = psutil.virtual_memory().percent
                    self.title = f" {cpu:.0f}% · {mem:.0f}%"
                self.title = None

            self._monitor_thread = threading.Thread(
                target=_monitor,
                daemon=True,
            )
            self._monitor_thread.start()
            rumps.notification(
                "OptiMac",
                "Monitoring",
                "Live CPU/RAM in menu bar",
            )

    # ══════════════════════════════════════════════════════════
    #  Utility Items
    # ══════════════════════════════════════════════════════════

    def _open_config(self, _):
        config_file = Path.home() / ".optimac" / "config.json"
        if config_file.exists():
            import subprocess

            subprocess.Popen(["open", str(config_file)])
        else:
            show_result(
                "Config File",
                "No config file found.",
                "Create one at ~/.optimac/config.json\n"
                "or use the MCP server to configure.",
            )

    def _toggle_terminal(self, sender):
        self.terminal.toggle()
        if self.terminal.is_visible():
            sender.title = "Hide Terminal"
        else:
            sender.title = "Show Terminal"

    def _on_terminal_closed(self):
        """Called when the terminal panel is closed via ✕ button."""
        self.terminal_toggle.title = "Show Terminal"

    def _quit(self, _):
        self._monitoring = False
        rumps.quit_application()


def main():
    """Entry point for the OptiMac menu bar application."""
    app = OptiMacMenuBar()
    app.run()


if __name__ == "__main__":
    main()
