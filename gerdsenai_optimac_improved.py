#!/usr/bin/env python3
"""
GerdsenAI OptiMac - Improved Mac Performance Optimizer
Enhanced performance monitoring and optimization for Apple Silicon Macs
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import queue
import time
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import platform
import math
import random
import multiprocessing
import socket
import psutil


class AppleSiliconMonitor:
    def __init__(self):
        self.chip_info = self.detect_chip()

    def detect_chip(self):
        """Detect Apple Silicon chip model and capabilities"""
        info = {
            "model": "Unknown",
            "generation": 0,
            "cpu_cores": 0,
            "gpu_cores": 0,
            "neural_cores": 16,
            "memory_bandwidth": 0,
            "perf_cores": 0,
            "eff_cores": 0,
        }

        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if "Apple M" in result.stdout:
                match = re.search(r"Apple M(\d+)( Pro| Max| Ultra)?", result.stdout)
                if match:
                    generation = int(match.group(1))
                    variant = match.group(2) or ""

                    info["model"] = f"M{generation}{variant.strip()}"
                    info["generation"] = generation
                    info.update(self.get_chip_capabilities(info["model"]))

            # Get actual core counts and try to get GPU cores more accurately
            try:
                perf_cores = int(
                    subprocess.check_output(
                        ["sysctl", "-n", "hw.perflevel0.physicalcpu"]
                    )
                    .decode()
                    .strip()
                )
                eff_cores = int(
                    subprocess.check_output(
                        ["sysctl", "-n", "hw.perflevel1.physicalcpu"]
                    )
                    .decode()
                    .strip()
                )
                info["cpu_cores"] = perf_cores + eff_cores
                info["perf_cores"] = perf_cores
                info["eff_cores"] = eff_cores

                # Try to get more accurate GPU core count
                gpu_result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                gpu_cores_detected = False

                # Method 1: Look for "Total Number of Cores"
                if "Total Number of Cores" in gpu_result.stdout:
                    match = re.search(
                        r"Total Number of Cores:\s*(\d+)", gpu_result.stdout
                    )
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True

                # Method 2: Look for GPU cores in different format
                if not gpu_cores_detected and "GPU Cores" in gpu_result.stdout:
                    match = re.search(r"GPU Cores:\s*(\d+)", gpu_result.stdout)
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True

                # Method 3: Try to parse Metal info
                if not gpu_cores_detected and "Metal" in gpu_result.stdout:
                    # Look for core count in Metal capabilities
                    metal_match = re.search(
                        r"(\d+)\s*(?:GPU\s*)?[Cc]ores?", gpu_result.stdout
                    )
                    if metal_match:
                        info["gpu_cores"] = int(metal_match.group(1))
                        gpu_cores_detected = True

            except (subprocess.SubprocessError, ValueError, OSError):
                info["cpu_cores"] = os.cpu_count() or 8

        except Exception as e:
            print(f"Chip detection error: {e}")

        return info

    def get_chip_capabilities(self, model):
        """Get known capabilities for specific chip models"""
        capabilities = {
            "M1": {
                "gpu_cores": 7,
                "memory_bandwidth": 68.25,
                "neural_tops": 11,
            },
            "M1 Pro": {
                "gpu_cores": 14,
                "memory_bandwidth": 200,
                "neural_tops": 11,
            },
            "M1 Max": {
                "gpu_cores": 24,
                "memory_bandwidth": 400,
                "neural_tops": 11,
            },
            "M1 Ultra": {
                "gpu_cores": 48,
                "memory_bandwidth": 800,
                "neural_tops": 22,
            },
            "M2": {
                "gpu_cores": 8,
                "memory_bandwidth": 100,
                "neural_tops": 15.8,
            },
            "M2 Pro": {
                "gpu_cores": 16,
                "memory_bandwidth": 200,
                "neural_tops": 15.8,
            },
            "M2 Max": {
                "gpu_cores": 30,
                "memory_bandwidth": 400,
                "neural_tops": 15.8,
            },
            "M2 Ultra": {
                "gpu_cores": 60,
                "memory_bandwidth": 800,
                "neural_tops": 31.6,
            },
            "M3": {
                "gpu_cores": 8,
                "memory_bandwidth": 100,
                "neural_tops": 18,
            },
            "M3 Pro": {
                "gpu_cores": 14,
                "memory_bandwidth": 150,
                "neural_tops": 18,
            },
            "M3 Max": {
                "gpu_cores": 30,
                "memory_bandwidth": 400,
                "neural_tops": 18,
            },
            "M4": {
                "gpu_cores": 8,
                "memory_bandwidth": 120,
                "neural_tops": 38,
            },
            "M4 Pro": {
                "gpu_cores": 16,
                "memory_bandwidth": 273,
                "neural_tops": 38,
            },
            "M4 Max": {
                "gpu_cores": 32,
                "memory_bandwidth": 546,
                "neural_tops": 38,
            },
        }

        # Try to detect actual GPU cores from system_profiler
        try:
            not_known = (
                model not in capabilities or "gpu_cores" not in capabilities[model]
            )
            if not_known:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "Total Number of Cores" in result.stdout:
                    match = re.search(r"Total Number of Cores:\s*(\d+)", result.stdout)
                    if match:
                        actual_cores = int(match.group(1))
                        if model in capabilities:
                            capabilities[model]["gpu_cores"] = actual_cores
                        else:
                            capabilities[model] = {
                                "gpu_cores": actual_cores,
                                "memory_bandwidth": 100,
                                "neural_tops": 15,
                            }
        except (subprocess.SubprocessError, ValueError, OSError):
            pass

        return capabilities.get(
            model, {"gpu_cores": 8, "memory_bandwidth": 100, "neural_tops": 15}
        )

    def get_powermetrics_data(self, duration=1):
        """Get power consumption data for CPU, GPU, and ANE"""
        if os.geteuid() != 0:
            return {"cpu_power": "N/A", "gpu_power": "N/A", "ane_power": "N/A"}

        cmd = [
            "powermetrics",
            "-i",
            str(duration * 1000),
            "-n",
            "1",
            "--samplers",
            "cpu_power,gpu_power,ane_power",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return self.parse_powermetrics(result.stdout)
        except Exception:
            return {"cpu_power": "N/A", "gpu_power": "N/A", "ane_power": "N/A"}

    def parse_powermetrics(self, output):
        """Parse powermetrics output for power values"""
        data = {"cpu_power": "N/A", "gpu_power": "N/A", "ane_power": "N/A"}

        patterns = {
            "cpu_power": r"CPU Power:\s*(\d+\.?\d*)\s*mW",
            "gpu_power": r"GPU Power:\s*(\d+\.?\d*)\s*mW",
            "ane_power": r"ANE Power:\s*(\d+\.?\d*)\s*mW",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                data[key] = f"{float(match.group(1)):.1f}mW"

        return data


class NetworkMonitor:
    def __init__(self):
        self.last_stats = None
        self.last_time = None
        self.primary_interface = self.get_primary_interface()

    def get_primary_interface(self):
        """Detect primary network interface on macOS"""
        try:
            result = subprocess.run(
                ["route", "get", "default"], capture_output=True, text=True
            )
            for line in result.stdout.split("\n"):
                if "interface:" in line:
                    return line.split(":")[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass

        # Fallback: return first active non-loopback interface
        interfaces = psutil.net_if_stats()
        for name, stats in interfaces.items():
            if stats.isup and not name.startswith("lo"):
                return name

        return "en0"

    def get_network_stats(self):
        """Get current network statistics"""
        try:
            current_time = time.time()

            # Get stats for all interfaces
            stats = psutil.net_io_counters(pernic=True)
            primary_stats = stats.get(self.primary_interface)

            if not primary_stats:
                return {
                    "interface": self.primary_interface,
                    "bytes_sent": "N/A",
                    "bytes_recv": "N/A",
                    "upload_rate": "N/A",
                    "download_rate": "N/A",
                }

            # Calculate rates if we have previous data
            upload_rate = download_rate = "N/A"
            if self.last_stats and self.last_time:
                time_delta = current_time - self.last_time
                if time_delta > 0:
                    upload_rate = (
                        primary_stats.bytes_sent - self.last_stats.bytes_sent
                    ) / time_delta
                    download_rate = (
                        primary_stats.bytes_recv - self.last_stats.bytes_recv
                    ) / time_delta
                    upload_rate = self.format_bytes(upload_rate) + "/s"
                    download_rate = self.format_bytes(download_rate) + "/s"

            # Store current stats for next calculation
            self.last_stats = primary_stats
            self.last_time = current_time

            return {
                "interface": self.primary_interface,
                "bytes_sent": self.format_bytes(primary_stats.bytes_sent),
                "bytes_recv": self.format_bytes(primary_stats.bytes_recv),
                "upload_rate": upload_rate,
                "download_rate": download_rate,
            }

        except Exception:
            return {
                "interface": "Error",
                "bytes_sent": "N/A",
                "bytes_recv": "N/A",
                "upload_rate": "N/A",
                "download_rate": "N/A",
            }

    def format_bytes(self, bytes_val):
        """Format bytes to human readable"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}PB"


class StressTestEngine:
    def __init__(self, chip_info):
        self.chip_info = chip_info
        self.stress_running = False

    def cpu_stress_worker(self, worker_id, duration, stop_event):
        """CPU-intensive workload using multiple algorithms"""
        start_time = time.time()
        operations = 0

        running = not stop_event.is_set()
        while running and (time.time() - start_time) < duration:
            # Prime number calculation
            n = 982451653
            all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1))

            # Floating point operations
            sum(
                math.sin(i) * math.cos(i) * math.sqrt(i + 1) for i in range(1000)
            )  # noqa: E501

            # Matrix ops (lightweight, no numpy)
            if operations % 10 == 0:
                a = [[random.random() for _ in range(50)] for _ in range(50)]
                b = [[random.random() for _ in range(50)] for _ in range(50)]
                # Partial matrix multiplication
                [
                    [
                        sum(a[i][k] * b[k][j] for k in range(50)) for j in range(25)
                    ]  # noqa: E501
                    for i in range(25)
                ]
            running = not stop_event.is_set()

            operations += 1

            # Yield periodically
            if operations % 100 == 0:
                time.sleep(0.001)

        return operations

    def memory_stress_worker(self, target_mb):
        """Memory allocation stress"""
        allocated_blocks = []
        block_size = 1024 * 1024  # 1MB blocks

        try:
            for i in range(target_mb):
                block = bytearray(block_size)
                # Fill with pattern to prevent compression
                for j in range(0, block_size, 4096):
                    block[j:j + 8] = (i * j).to_bytes(8, "little")
                allocated_blocks.append(block)

                # Prevent unlimited growth
                if len(allocated_blocks) > 100:
                    allocated_blocks.pop(0)

        except MemoryError:
            pass

        return len(allocated_blocks)


class AIStackManager:
    """Manage AI inference services (Ollama, LM Studio, MLX)"""

    SERVICES = {
        "ollama": {"port": 11434, "binary": "ollama"},
        "lmstudio": {"port": 1234, "binary": "lms"},
        "mlx": {"port": 8080, "binary": "mlx_lm.server"},
    }

    def check_port(self, port, host="127.0.0.1", timeout=1):
        """Check if a port is open"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((host, port)) == 0
        except OSError:
            return False

    def is_installed(self, service_name):
        """Check if a service binary is installed"""
        binary = self.SERVICES.get(service_name, {}).get("binary")
        if not binary:
            return False
        try:
            subprocess.run(["which", binary], capture_output=True, timeout=3)
            return True
        except (subprocess.SubprocessError, OSError):
            return False

    def get_status(self, service_name):
        """Get service status: running, stopped, or not_installed"""
        info = self.SERVICES.get(service_name)
        if not info:
            return "unknown"
        if self.check_port(info["port"]):
            return "running"
        if not self.is_installed(service_name):
            return "not_installed"
        return "stopped"

    def get_all_status(self):
        """Get status of all services"""
        return {name: self.get_status(name) for name in self.SERVICES}

    def start_service(self, service_name):
        """Start a service"""
        if service_name == "ollama":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "Ollama server starting..."
        elif service_name == "lmstudio":
            subprocess.Popen(
                ["lms", "server", "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "LM Studio server starting..."
        elif service_name == "mlx":
            return "Start MLX via: mlx_lm.server --model <model> --port 8080"
        return f"Unknown service: {service_name}"

    def stop_service(self, service_name):
        """Stop a service"""
        if service_name == "ollama":
            subprocess.run(
                ["pkill", "-f", "ollama serve"], capture_output=True, timeout=5
            )
            return "Ollama server stopped"
        elif service_name == "lmstudio":
            subprocess.run(["lms", "server", "stop"], capture_output=True, timeout=5)
            return "LM Studio server stopped"
        elif service_name == "mlx":
            subprocess.run(
                ["pkill", "-f", "mlx_lm.server"],
                capture_output=True,
                timeout=5,  # noqa: E501
            )
            return "MLX server stopped"
        return f"Unknown service: {service_name}"

    def list_ollama_models(self):
        """List installed Ollama models"""
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.stdout else "No models"
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return "Ollama not available"

    def pull_ollama_model(self, model_name):
        """Pull an Ollama model (returns Popen for background)"""
        try:
            proc = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return proc
        except (OSError, FileNotFoundError):
            return None


class ConfigManager:
    """Manage OptiMac configuration at ~/.optimac/config.json"""

    DEFAULT_CONFIG = {
        "protectedProcesses": [
            "ollama",
            "lmstudio",
            "mlx_lm",
            "claude",
            "Finder",
            "WindowServer",
            "loginwindow",
        ],
        "memoryThresholds": {"warning": 75, "critical": 90, "autoKill": 95},
        "aiStackPorts": {"ollama": 11434, "lmstudio": 1234, "mlx": 8080},
        "dnsServers": ["1.1.1.1", "1.0.0.1"],
        "maintenanceInterval": 3600,
    }

    def __init__(self):
        self.config_dir = Path.home() / ".optimac"
        self.config_file = self.config_dir / "config.json"

    def load(self):
        """Load config, creating defaults if missing"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self.DEFAULT_CONFIG)

    def save(self, config):
        """Save config to disk"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def add_protected(self, process_name):
        """Add a process to protected list"""
        config = self.load()
        procs = config.get("protectedProcesses", [])
        if process_name not in procs:
            procs.append(process_name)
            config["protectedProcesses"] = procs
            self.save(config)
        return procs

    def remove_protected(self, process_name):
        """Remove a process from protected list"""
        config = self.load()
        procs = config.get("protectedProcesses", [])
        if process_name in procs:
            procs.remove(process_name)
            config["protectedProcesses"] = procs
            self.save(config)
        return procs


class CommandExecutor:
    def __init__(self, terminal_widget):
        self.terminal = terminal_widget

    def execute_command(self, command, description=None):
        """Execute system command and display in terminal"""
        if description:
            self.terminal.write_output(f"{description}...", "warning")

        self.terminal.write_output(f"$ {command}", "command")

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )

            if result.stdout:
                # Filter out excessive output
                output_lines = result.stdout.strip().split("\n")
                if len(output_lines) > 10:
                    self.terminal.write_output(
                        f"Output: {len(output_lines)} lines processed",
                        "success",  # noqa: E501
                    )
                else:
                    self.terminal.write_output(
                        result.stdout.strip(), "success"
                    )  # noqa: E501

            if result.stderr:
                # Filter common harmless errors
                stderr_clean = result.stderr.strip()
                if not any(
                    harmless in stderr_clean.lower()
                    for harmless in [
                        "no such file",
                        "operation not permitted",
                        "permission denied",
                    ]
                ):
                    self.terminal.write_output(stderr_clean, "error")
                elif "permission denied" in stderr_clean.lower():
                    self.terminal.write_output(
                        "Permission denied - try running with sudo", "warning"
                    )
                else:
                    self.terminal.write_output(
                        "Command completed with warnings", "warning"
                    )

            if result.returncode == 0:
                self.terminal.write_output(
                    "Command completed successfully", "success"
                )  # noqa: E501

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.terminal.write_output("Command timed out", "error")
            return False
        except Exception as e:
            self.terminal.write_output(f"Error: {str(e)}", "error")
            return False


class GerdsenAIOptiMac:
    def __init__(self, root):
        self.root = root
        self.root.title("GerdsenAI OptiMac v2.0 - Terminal Edition")
        self.root.geometry("1200x850")
        self.root.configure(bg="#000000")

        # Retro terminal colors
        self.bg_color = "#000000"
        self.fg_color = "#00FF00"
        self.accent_color = "#00FF66"
        self.warning_color = "#FFFF00"
        self.error_color = "#FF0000"
        self.command_color = "#00FFFF"

        # Initialize components
        self.silicon_monitor = AppleSiliconMonitor()
        self.network_monitor = NetworkMonitor()
        self.stress_engine = StressTestEngine(self.silicon_monitor.chip_info)
        self.ai_manager = AIStackManager()
        self.config_manager = ConfigManager()

        # State variables
        self.monitoring = False
        self.stress_testing = False
        self.output_queue = queue.Queue()
        self.stress_duration = 30

        # Create GUI
        self.configure_styles()
        self.create_interface()
        self.start_queue_processor()

        # Check sudo status
        self.check_sudo_status()

    def configure_styles(self):
        """Configure ttk styles for dark retro theme"""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=self.bg_color, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background="#001a00",
            foreground=self.fg_color,
            padding=[14, 6],
            font=("Courier New", 9, "bold"),
            borderwidth=1,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", "#003300"), ("active", "#002200")],
            foreground=[("selected", self.accent_color), ("active", self.fg_color)],
        )
        style.configure(
            "Dark.TLabelframe",
            background=self.bg_color,
            foreground=self.fg_color,
            font=("Courier New", 9, "bold"),
        )
        style.configure(
            "Dark.TLabelframe.Label",
            background=self.bg_color,
            foreground=self.accent_color,
            font=("Courier New", 9, "bold"),
        )

    def create_interface(self):
        """Create retro terminal interface with tabs"""
        # ASCII Banner
        self.create_banner()

        # System info
        self.create_system_info()

        # Tabbed notebook for controls
        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10)

        # Create tabs
        self.create_dashboard_tab()
        self.create_tests_tab()
        self.create_optimize_tab()
        self.create_ai_tab()
        self.create_maintenance_tab()

        # Status bar
        self.create_status_bar()

    def create_banner(self):
        """Create ASCII art banner"""
        banner_frame = tk.Frame(self.root, bg=self.bg_color)
        banner_frame.pack(fill="x", padx=10, pady=5)

        banner_text = """
 ██████╗ ███████╗██████╗ ██████╗ ███████╗███████╗███╗   ██╗ █████╗ ██╗
██╔════╝ ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝████╗  ██║██╔══██╗██║
██║  ███╗█████╗  ██████╔╝██║  ██║███████╗█████╗  ██╔██╗ ██║███████║██║
██║   ██║██╔══╝  ██╔══██╗██║  ██║╚════██║██╔══╝  ██║╚██╗██║██╔══██║██║
╚██████╔╝███████╗██║  ██║██████╔╝███████║███████╗██║ ╚████║██║  ██║██║
 ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝

                    O P T I M A C   v 2 . 0   T E R M I N A L
        """

        banner_label = tk.Label(
            banner_frame,
            text=banner_text,
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Courier New", 7, "bold"),
            justify="left",
        )
        banner_label.pack()

    def create_system_info(self):
        """Create system information display"""
        info_frame = tk.Frame(self.root, bg=self.bg_color)
        info_frame.pack(fill="x", padx=10, pady=5)

        chip = self.silicon_monitor.chip_info
        info_text = (
            f"SYSTEM: Apple {chip['model']} | "
            f"CPU: {chip.get('perf_cores', 'N/A')}P+"
            f"{chip.get('eff_cores', 'N/A')}E cores | "
            f"GPU: {chip.get('gpu_cores', 'N/A')} cores | "
            f"NPU: {chip['neural_cores']} cores "
            f"({chip.get('neural_tops', 'N/A')} TOPS)"
        )

        info_label = tk.Label(
            info_frame,
            text=info_text,
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 10, "bold"),
        )
        info_label.pack()

    def _btn_config(self):
        """Standard button style config"""
        return {
            "bg": "#002200",
            "fg": self.fg_color,
            "font": ("Courier New", 10, "bold"),
            "relief": "raised",
            "bd": 2,
            "padx": 12,
            "pady": 6,
            "activebackground": "#004400",
            "activeforeground": self.accent_color,
        }

    def _make_btn(self, parent, text, command):
        """Create a styled button with hover effects"""
        btn = tk.Button(parent, text=text, command=command, **self._btn_config())
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#004400"))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#002200"))
        return btn

    def _make_tab_frame(self, title):
        """Create a tab frame and add it to the notebook"""
        frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(frame, text=f" {title} ")
        return frame

    def _make_tab_terminal(self, parent, height=12):
        """Create a terminal output widget inside a tab"""
        term = scrolledtext.ScrolledText(
            parent,
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            font=("Courier New", 10),
            wrap=tk.WORD,
            height=height,
            state="disabled",
            cursor="arrow",
        )
        for tag, color in [
            ("command", self.command_color),
            ("error", self.error_color),
            ("warning", self.warning_color),
            ("success", self.fg_color),
            ("accent", self.accent_color),
        ]:
            term.tag_config(tag, foreground=color)
        return term

    def _write_to(self, terminal, text, tag="success"):
        """Write text to a specific terminal widget"""
        ts = datetime.now().strftime("%H:%M:%S")
        terminal.config(state="normal")
        terminal.insert("end", f"[{ts}] {text}\n", tag)
        terminal.see("end")
        terminal.config(state="disabled")

    # ---- Tab 1: Dashboard ----

    def create_dashboard_tab(self):
        """Dashboard tab with monitoring controls"""
        tab = self._make_tab_frame("DASHBOARD")

        # Controls row
        ctrl = tk.Frame(tab, bg=self.bg_color)
        ctrl.pack(fill="x", padx=5, pady=5)

        btn = self._make_btn(ctrl, "START MONITOR", self.toggle_monitoring)
        btn.pack(side="left", padx=3)
        btn = self._make_btn(ctrl, "CLEAR", self.clear_terminal)
        btn.pack(side="left", padx=3)
        btn = self._make_btn(ctrl, "EXIT", self.quit_app)
        btn.pack(side="right", padx=3)

        # Terminal
        self.terminal_output = self._make_tab_terminal(tab, height=20)
        self.terminal_output.pack(fill="both", expand=True, padx=5, pady=5)

        # Initialize command executor with main terminal
        self.command_executor = CommandExecutor(self)

        # Welcome message
        self.write_output("GerdsenAI OptiMac Terminal v2.0 Initialized", "accent")
        self.write_output("Ready for optimization and monitoring", "success")

    # ---- Tab 2: Stress Tests ----

    def create_tests_tab(self):
        """Stress testing tab"""
        tab = self._make_tab_frame("STRESS TESTS")

        # Duration selector
        dur_frame = tk.Frame(tab, bg=self.bg_color)
        dur_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(
            dur_frame,
            text="DURATION:",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)

        self.duration_var = tk.StringVar(value="30s")
        for val in ["10s", "30s", "60s", "120s"]:
            rb = tk.Radiobutton(
                dur_frame,
                text=val,
                variable=self.duration_var,
                value=val,
                bg=self.bg_color,
                fg=self.fg_color,
                selectcolor="#003300",
                activebackground=self.bg_color,
                activeforeground=self.accent_color,
                font=("Courier New", 10),
                command=self._update_duration,
            )
            rb.pack(side="left", padx=5)

        # Test buttons
        btn_frame = tk.Frame(tab, bg=self.bg_color)
        btn_frame.pack(fill="x", padx=5, pady=5)

        for text, cmd in [
            ("CPU TEST", self.run_cpu_stress),
            ("MEMORY TEST", self.run_memory_stress),
            ("COMBINED TEST", self.run_combined_stress),
        ]:
            btn = self._make_btn(btn_frame, text, cmd)
            btn.pack(side="left", padx=3)

        # Test output terminal
        self.test_terminal = self._make_tab_terminal(tab, height=18)
        self.test_terminal.pack(fill="both", expand=True, padx=5, pady=5)

    def _update_duration(self):
        """Update stress test duration from selector"""
        val = self.duration_var.get().rstrip("s")
        self.stress_duration = int(val)

    # ---- Tab 3: System Optimization ----

    def create_optimize_tab(self):
        """System optimization tab"""
        tab = self._make_tab_frame("OPTIMIZE")

        # Quick actions
        qa_frame = tk.LabelFrame(
            tab,
            text=" Quick Actions ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        )
        qa_frame.pack(fill="x", padx=5, pady=3)

        actions = [
            ("PURGE MEM", self._purge_memory),
            ("FLUSH DNS", self._flush_dns),
            ("FLUSH ROUTES", self._flush_routes),
            ("CLEAR CACHES", self._clear_caches),
        ]
        for text, cmd in actions:
            btn = self._make_btn(qa_frame, text, cmd)
            btn.pack(side="left", padx=3, pady=3)

        # Power profiles
        pwr_frame = tk.LabelFrame(
            tab,
            text=" Power Profile ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        )
        pwr_frame.pack(fill="x", padx=5, pady=3)

        self.power_var = tk.StringVar(value="default")
        for val, label in [
            ("default", "Default"),
            ("ai_server", "AI Server"),
            ("low_power", "Low Power"),
        ]:
            rb = tk.Radiobutton(
                pwr_frame,
                text=label,
                variable=self.power_var,
                value=val,
                bg=self.bg_color,
                fg=self.fg_color,
                selectcolor="#003300",
                activebackground=self.bg_color,
                activeforeground=self.accent_color,
                font=("Courier New", 10),
            )
            rb.pack(side="left", padx=5, pady=3)

        btn = self._make_btn(pwr_frame, "APPLY", self._apply_power_profile)
        btn.pack(side="left", padx=10, pady=3)

        # Spotlight + DNS row
        misc_frame = tk.Frame(tab, bg=self.bg_color)
        misc_frame.pack(fill="x", padx=5, pady=3)

        btn = self._make_btn(
            misc_frame,
            "DISABLE SPOTLIGHT",
            lambda: self._run_opt_cmd("sudo mdutil -a -i off", "Disabling Spotlight"),
        )
        btn.pack(side="left", padx=3)
        btn = self._make_btn(
            misc_frame,
            "ENABLE SPOTLIGHT",
            lambda: self._run_opt_cmd("sudo mdutil -a -i on", "Enabling Spotlight"),
        )
        btn.pack(side="left", padx=3)
        btn = self._make_btn(
            misc_frame,
            "SET DNS CLOUDFLARE",
            lambda: self._run_opt_cmd(
                "networksetup -setdnsservers Wi-Fi" " 1.1.1.1 1.0.0.1",
                "Setting DNS to Cloudflare",
            ),
        )
        btn.pack(side="left", padx=3)

        # Full optimize button
        btn = self._make_btn(tab, "RUN FULL OPTIMIZE", self.run_optimization)
        btn.pack(padx=5, pady=3, anchor="w")

        # Optimize terminal
        self.opt_terminal = self._make_tab_terminal(tab, height=14)
        self.opt_terminal.pack(fill="both", expand=True, padx=5, pady=5)

    # ---- Tab 4: AI Stack ----

    def create_ai_tab(self):
        """AI stack management tab"""
        tab = self._make_tab_frame("AI STACK")

        # Status display
        status_frame = tk.LabelFrame(
            tab,
            text=" Service Status ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        )
        status_frame.pack(fill="x", padx=5, pady=3)

        self.ai_status_labels = {}
        for svc in ["ollama", "lmstudio", "mlx"]:
            row = tk.Frame(status_frame, bg=self.bg_color)
            row.pack(fill="x", padx=5, pady=2)

            tk.Label(
                row,
                text=f"{svc.upper()}:",
                bg=self.bg_color,
                fg=self.fg_color,
                font=("Courier New", 10, "bold"),
                width=12,
                anchor="w",
            ).pack(side="left")

            lbl = tk.Label(
                row,
                text="checking...",
                bg=self.bg_color,
                fg=self.warning_color,
                font=("Courier New", 10),
                anchor="w",
            )
            lbl.pack(side="left", padx=5)
            self.ai_status_labels[svc] = lbl

            self._make_btn(row, "START", lambda s=svc: self._ai_start(s)).pack(
                side="left", padx=2
            )
            self._make_btn(row, "STOP", lambda s=svc: self._ai_stop(s)).pack(
                side="left", padx=2
            )

        # Refresh + Models
        ctrl_frame = tk.Frame(tab, bg=self.bg_color)
        ctrl_frame.pack(fill="x", padx=5, pady=3)

        self._make_btn(
            ctrl_frame, "REFRESH STATUS", self._refresh_ai_status
        ).pack(  # noqa: E501
            side="left", padx=3
        )
        self._make_btn(ctrl_frame, "LIST MODELS", self._list_models).pack(
            side="left", padx=3
        )

        # Model pull
        pull_frame = tk.Frame(tab, bg=self.bg_color)
        pull_frame.pack(fill="x", padx=5, pady=3)

        tk.Label(
            pull_frame,
            text="PULL MODEL:",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)

        self.model_entry = tk.Entry(
            pull_frame,
            bg="#001100",
            fg=self.fg_color,
            insertbackground=self.fg_color,
            font=("Courier New", 10),
            width=30,
        )
        self.model_entry.pack(side="left", padx=3)

        self._make_btn(pull_frame, "PULL", self._pull_model).pack(side="left", padx=3)

        # AI terminal
        self.ai_terminal = self._make_tab_terminal(tab, height=14)
        self.ai_terminal.pack(fill="both", expand=True, padx=5, pady=5)

        # Initial status check
        self.root.after(500, self._refresh_ai_status)

    # ---- Tab 5: Maintenance & Config ----

    def create_maintenance_tab(self):
        """Maintenance and configuration tab"""
        tab = self._make_tab_frame("MAINTENANCE")

        # Maintenance buttons
        maint_frame = tk.LabelFrame(
            tab,
            text=" Maintenance ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        )
        maint_frame.pack(fill="x", padx=5, pady=3)

        self._make_btn(
            maint_frame, "RUN MAINTENANCE CYCLE", self._run_maintenance
        ).pack(side="left", padx=3, pady=3)
        self._make_btn(
            maint_frame, "MEMORY PRESSURE CHECK", self._check_memory_pressure
        ).pack(side="left", padx=3, pady=3)
        self._make_btn(maint_frame, "VIEW CONFIG", self._view_config).pack(
            side="left", padx=3, pady=3
        )

        # Protected processes
        prot_frame = tk.LabelFrame(
            tab,
            text=" Protected Processes ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        )
        prot_frame.pack(fill="x", padx=5, pady=3)

        list_frame = tk.Frame(prot_frame, bg=self.bg_color)
        list_frame.pack(fill="x", padx=5, pady=3)

        self.prot_listbox = tk.Listbox(
            list_frame,
            bg="#001100",
            fg=self.fg_color,
            font=("Courier New", 10),
            height=4,
            selectbackground="#003300",
        )
        self.prot_listbox.pack(side="left", fill="x", expand=True)

        btn_col = tk.Frame(list_frame, bg=self.bg_color)
        btn_col.pack(side="left", padx=5)

        self._make_btn(btn_col, "ADD", self._add_protected).pack(pady=2)
        self._make_btn(btn_col, "REMOVE", self._remove_protected).pack(pady=2)

        # Entry for adding
        add_frame = tk.Frame(prot_frame, bg=self.bg_color)
        add_frame.pack(fill="x", padx=5, pady=3)

        self.prot_entry = tk.Entry(
            add_frame,
            bg="#001100",
            fg=self.fg_color,
            insertbackground=self.fg_color,
            font=("Courier New", 10),
            width=30,
        )
        self.prot_entry.pack(side="left", padx=3)

        # Maintenance terminal
        self.maint_terminal = self._make_tab_terminal(tab, height=12)
        self.maint_terminal.pack(fill="both", expand=True, padx=5, pady=5)

        # Load protected processes
        self._load_protected_list()

    def create_status_bar(self):
        """Create status bar"""
        status_frame = tk.Frame(self.root, bg="#001100", height=30)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            status_frame,
            text="READY",
            bg="#001100",
            fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        )
        self.status_label.pack(side="left", padx=10, pady=5)

        self.sudo_label = tk.Label(
            status_frame,
            text="",
            bg="#001100",
            fg=self.warning_color,
            font=("Courier New", 10),
        )
        self.sudo_label.pack(side="right", padx=10, pady=5)

    def write_output(self, text, tag="success"):
        """Write text to terminal with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.config(state="normal")
        self.terminal_output.insert("end", f"[{timestamp}] {text}\n", tag)
        self.terminal_output.see("end")
        self.terminal_output.config(state="disabled")

    def check_sudo_status(self):
        """Check if running with sudo privileges"""
        if os.geteuid() != 0:
            self.sudo_label.config(text="NO SUDO - LIMITED FEATURES")
            self.write_output(
                "WARNING: Not running as sudo - some features limited",
                "warning",  # noqa: E501
            )
        else:
            self.sudo_label.config(text="SUDO ACTIVE")
            self.write_output("Running with administrator privileges", "accent")

    def toggle_monitoring(self):
        """Toggle system monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.status_label.config(text="MONITORING ACTIVE")
            self.write_output("Starting system monitoring...", "accent")

            thread = threading.Thread(target=self.monitor_system)
            thread.daemon = True
            thread.start()
        else:
            self.monitoring = False
            self.status_label.config(text="MONITORING STOPPED")
            self.write_output("Monitoring stopped", "warning")

    def monitor_system(self):
        """System monitoring loop"""
        while self.monitoring:
            try:
                # Get system stats
                stats = self.collect_system_stats()
                self.output_queue.put(("monitor_display", stats))
                time.sleep(2)
            except Exception as e:
                self.output_queue.put(("monitor_error", str(e)))
                time.sleep(5)

    def collect_system_stats(self):
        """Collect comprehensive system statistics"""
        stats = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "cpu_usage": "N/A",
            "memory": {"used": "N/A", "total": "N/A", "percent": "N/A"},
            "power": {"cpu": "N/A", "gpu": "N/A", "npu": "N/A"},
            "network": {"up": "N/A", "down": "N/A"},
            "temperature": "N/A",
        }

        # CPU usage
        try:
            stats["cpu_usage"] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
        except (AttributeError, OSError):
            pass

        # Memory usage
        try:
            mem = psutil.virtual_memory()
            stats["memory"] = {
                "used": self.network_monitor.format_bytes(mem.used),
                "total": self.network_monitor.format_bytes(mem.total),
                "percent": f"{mem.percent:.1f}%",
            }
        except (AttributeError, OSError):
            pass

        # Power consumption (requires sudo)
        if os.geteuid() == 0:
            power_data = self.silicon_monitor.get_powermetrics_data()
            stats["power"] = {
                "cpu": power_data.get("cpu_power", "N/A"),
                "gpu": power_data.get("gpu_power", "N/A"),
                "npu": power_data.get("ane_power", "N/A"),
            }

        # Network stats
        try:
            net_stats = self.network_monitor.get_network_stats()
            stats["network"] = {
                "up": net_stats.get("upload_rate", "N/A"),
                "down": net_stats.get("download_rate", "N/A"),
            }
        except (AttributeError, OSError):
            pass

        # Temperature (requires sudo)
        if os.geteuid() == 0:
            try:
                result = subprocess.run(
                    ["sudo", "powermetrics", "--samplers", "smc", "-n", "1"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                for line in result.stdout.split("\n"):
                    if "CPU die temperature" in line:
                        stats["temperature"] = line.split(":")[1].strip()
                        break
            except (subprocess.SubprocessError, OSError):
                pass

        return stats

    def display_monitor_stats(self, stats):
        """Display monitoring statistics"""
        display_text = f"""
SYSTEM MONITOR [{stats['timestamp']}]
==========================================
CPU Usage:    {stats['cpu_usage']}
Memory:       {stats['memory']['used']} / {stats['memory']['total']} ({stats['memory']['percent']})  # noqa: E501
Temperature:  {stats['temperature']}

POWER CONSUMPTION
CPU Power:    {stats['power']['cpu']}
GPU Power:    {stats['power']['gpu']}
NPU Power:    {stats['power']['npu']}

NETWORK ({self.network_monitor.primary_interface})
Upload:       {stats['network']['up']}
Download:     {stats['network']['down']}
==========================================
        """
        self.write_output(display_text.strip(), "accent")

    def run_cpu_stress(self):
        """Run CPU stress test"""
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return

        self.stress_testing = True
        dur = self.stress_duration
        self.status_label.config(text="CPU STRESS TEST")
        self._write_to(
            self.test_terminal,
            f"Starting CPU stress test ({dur}s)...",
            "warning",  # noqa: E501
        )

        thread = threading.Thread(target=self.cpu_stress_test)
        thread.daemon = True
        thread.start()

    def cpu_stress_test(self):
        """CPU stress test implementation"""
        try:
            duration = self.stress_duration
            cores_to_use = self.silicon_monitor.chip_info["cpu_cores"]

            self.output_queue.put(
                ("stress_update", f"Utilizing {cores_to_use} CPU cores")
            )

            stop_event = multiprocessing.Event()
            processes = []

            for i in range(cores_to_use):
                p = multiprocessing.Process(
                    target=self.stress_engine.cpu_stress_worker,
                    args=(i, duration, stop_event),
                )
                p.start()
                processes.append(p)

            # Monitor progress
            for i in range(duration):
                if not self.stress_testing:
                    stop_event.set()
                    break
                self.output_queue.put(
                    (
                        "stress_update",
                        f"CPU test progress: {i+1}/{duration} seconds",
                    )  # noqa: E501
                )
                time.sleep(1)

            # Cleanup
            stop_event.set()
            for p in processes:
                p.join(timeout=5)
                if p.is_alive():
                    p.terminate()

            self.output_queue.put(("stress_complete", "CPU stress test completed"))

        except Exception as e:
            self.output_queue.put(("stress_error", f"CPU stress test error: {e}"))
        finally:
            self.stress_testing = False

    def run_memory_stress(self):
        """Run memory stress test"""
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return

        self.stress_testing = True
        self.status_label.config(text="MEMORY STRESS TEST")
        self._write_to(self.test_terminal, "Starting memory stress test...", "warning")

        thread = threading.Thread(target=self.memory_stress_test)
        thread.daemon = True
        thread.start()

    def memory_stress_test(self):
        """Memory stress test implementation"""
        try:
            available_mb = psutil.virtual_memory().available // (1024 * 1024)
            target_mb = min(available_mb // 2, 1000)  # Use half available or 1GB max

            self.output_queue.put(
                ("stress_update", f"Allocating {target_mb}MB of memory")
            )

            result = self.stress_engine.memory_stress_worker(target_mb)

            self.output_queue.put(
                (
                    "stress_complete",
                    f"Memory test completed - allocated {result}MB",
                )  # noqa: E501
            )

        except Exception as e:
            self.output_queue.put(("stress_error", f"Memory stress test error: {e}"))
        finally:
            self.stress_testing = False

    def run_optimization(self):
        """Run system optimization"""
        self.status_label.config(text="OPTIMIZING SYSTEM")
        self.write_output("Starting system optimization...", "accent")

        thread = threading.Thread(target=self.optimization_thread)
        thread.daemon = True
        thread.start()

    def optimization_thread(self):
        """System optimization implementation"""
        if os.geteuid() == 0:
            # Commands for sudo mode
            commands = [
                (
                    "Clearing DNS cache",
                    "dscacheutil -flushcache && killall -HUP mDNSResponder",
                ),
                ("Purging inactive memory", "purge"),
                ("Enabling high performance mode", "pmset -a highpowermode 1"),
                ("Disabling sleep", "pmset -a sleep 0"),
                (
                    "Clearing system caches",
                    "rm -rf /System/Library/Caches/* 2>/dev/null || true",
                ),
                (
                    "Rebuilding font cache",
                    "atsutil databases -removeUser && atsutil server -shutdown && atsutil server -ping",  # noqa: E501
                ),
            ]
        else:
            # Commands for non-sudo mode (user-level optimizations)
            commands = [
                ("Clearing user DNS cache", "dscacheutil -flushcache"),
                (
                    "Clearing user caches",
                    "rm -rf ~/Library/Caches/com.apple.* 2>/dev/null || true",
                ),
                ("Clearing user font cache", "atsutil databases -removeUser"),
                ("Restarting Dock", "killall Dock"),
                (
                    "Clearing user logs",
                    "rm -rf ~/Library/Logs/* 2>/dev/null || true",
                ),  # noqa: E501
                (
                    "Restarting user services",
                    "launchctl kickstart -k gui/$(id -u)/com.apple.Dock",
                ),
            ]

        for description, cmd in commands:
            self.output_queue.put(("optimize_step", (description, cmd)))
            time.sleep(1)

        self.output_queue.put(("optimize_complete", "System optimization completed"))

    # ---- Combined stress test ----

    def run_combined_stress(self):
        """Run CPU + Memory stress test combined"""
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return

        self.stress_testing = True
        self.status_label.config(text="COMBINED STRESS TEST")
        self._write_to(
            self.test_terminal,
            f"Starting combined stress ({self.stress_duration}s)...",
            "warning",
        )

        def combined():
            try:
                dur = self.stress_duration
                cores = self.silicon_monitor.chip_info["cpu_cores"]
                self.output_queue.put(
                    (
                        "stress_update",
                        f"CPU: {cores} cores + Memory allocation",
                    )  # noqa: E501
                )

                stop = multiprocessing.Event()
                procs = []
                for i in range(cores):
                    p = multiprocessing.Process(
                        target=self.stress_engine.cpu_stress_worker,
                        args=(i, dur, stop),
                    )
                    p.start()
                    procs.append(p)

                avail = psutil.virtual_memory().available
                target = min(avail // (1024 * 1024) // 4, 512)
                self.output_queue.put(
                    ("stress_update", f"Allocating {target}MB memory")
                )
                self.stress_engine.memory_stress_worker(target)

                for i in range(dur):
                    if not self.stress_testing:
                        stop.set()
                        break
                    self.output_queue.put(("stress_update", f"Combined: {i+1}/{dur}s"))
                    time.sleep(1)

                stop.set()
                for p in procs:
                    p.join(timeout=5)
                    if p.is_alive():
                        p.terminate()

                self.output_queue.put(
                    ("stress_complete", "Combined stress test completed")
                )
            except Exception as e:
                self.output_queue.put(("stress_error", f"Combined test error: {e}"))
            finally:
                self.stress_testing = False

        t = threading.Thread(target=combined)
        t.daemon = True
        t.start()

    # ---- Optimization actions ----

    def _run_opt_cmd(self, cmd, description):
        """Run an optimization command in background"""

        def run():
            self._write_to(self.opt_terminal, f">> {description}...", "command")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    self._write_to(self.opt_terminal, f"   OK: {description}", "accent")
                else:
                    err = result.stderr.strip()[:100]
                    self._write_to(self.opt_terminal, f"   FAIL: {err}", "error")
            except Exception as e:
                self._write_to(self.opt_terminal, f"   ERROR: {e}", "error")

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _purge_memory(self):
        """Purge inactive memory"""
        self._run_opt_cmd("purge", "Purging inactive memory")

    def _flush_dns(self):
        """Flush DNS cache"""
        self._run_opt_cmd(
            "dscacheutil -flushcache && " "sudo killall -HUP mDNSResponder",
            "Flushing DNS cache",
        )

    def _flush_routes(self):
        """Flush routing table"""
        self._run_opt_cmd("sudo route -n flush", "Flushing network routes")

    def _clear_caches(self):
        """Clear user caches"""
        self._run_opt_cmd(
            "rm -rf ~/Library/Caches/com.apple.* " "2>/dev/null || true",
            "Clearing user caches",
        )

    def _apply_power_profile(self):
        """Apply selected power profile"""
        profile = self.power_var.get()
        if profile == "ai_server":
            cmds = (
                "sudo pmset -a sleep 0 && "
                "sudo pmset -a disksleep 0 && "
                "sudo pmset -a highpowermode 1"
            )
            desc = "Applying AI Server power profile"
        elif profile == "low_power":
            cmds = "sudo pmset -a lowpowermode 1 && " "sudo pmset -a sleep 10"
            desc = "Applying Low Power profile"
        else:
            cmds = "sudo pmset restoredefaults"
            desc = "Restoring default power profile"
        self._run_opt_cmd(cmds, desc)

    # ---- AI Stack actions ----

    def _ai_start(self, service):
        """Start an AI service"""

        def run():
            msg = self.ai_manager.start_service(service)
            self._write_to(self.ai_terminal, msg, "accent")
            time.sleep(2)
            self._refresh_ai_status()

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _ai_stop(self, service):
        """Stop an AI service"""

        def run():
            msg = self.ai_manager.stop_service(service)
            self._write_to(self.ai_terminal, msg, "warning")
            time.sleep(1)
            self._refresh_ai_status()

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _refresh_ai_status(self):
        """Refresh AI service status labels"""

        def run():
            statuses = self.ai_manager.get_all_status()
            for svc, status in statuses.items():
                lbl = self.ai_status_labels.get(svc)
                if not lbl:
                    continue
                color_map = {
                    "running": self.accent_color,
                    "stopped": self.error_color,
                    "not_installed": self.warning_color,
                }
                icon_map = {
                    "running": "● RUNNING",
                    "stopped": "○ STOPPED",
                    "not_installed": "✗ NOT INSTALLED",
                }
                color = color_map.get(status, self.fg_color)
                text = icon_map.get(status, status)
                lbl.config(text=text, fg=color)

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _list_models(self):
        """List installed Ollama models"""

        def run():
            self._write_to(self.ai_terminal, "Fetching Ollama models...", "command")
            out = self.ai_manager.list_ollama_models()
            for line in out.split("\n"):
                self._write_to(self.ai_terminal, f"  {line}", "accent")

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _pull_model(self):
        """Pull an Ollama model"""
        name = self.model_entry.get().strip()
        if not name:
            self._write_to(self.ai_terminal, "Enter a model name first", "warning")
            return

        def run():
            self._write_to(self.ai_terminal, f"Pulling model: {name}...", "command")
            proc = self.ai_manager.pull_ollama_model(name)
            if proc is None:
                self._write_to(self.ai_terminal, "Ollama not available", "error")
                return
            for line in proc.stdout:
                line = line.strip()
                if line:
                    self._write_to(self.ai_terminal, f"  {line}", "accent")
            proc.wait()
            if proc.returncode == 0:
                self._write_to(
                    self.ai_terminal,
                    f"Model {name} pulled successfully!",
                    "accent",  # noqa: E501
                )
            else:
                self._write_to(self.ai_terminal, f"Failed to pull {name}", "error")

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    # ---- Maintenance actions ----

    def _run_maintenance(self):
        """Run full maintenance cycle"""
        steps = [
            ("Check memory pressure", "memory_pressure"),
            ("Flush DNS cache", "dscacheutil -flushcache"),
            (
                "Clear user caches",
                "rm -rf ~/Library/Caches/com.apple.* " "2>/dev/null || true",
            ),
            ("Clear user logs", "rm -rf ~/Library/Logs/* 2>/dev/null || true"),
            ("Rebuild Spotlight index", "mdutil -E / 2>/dev/null || true"),
            ("Flush routes", "sudo route -n flush 2>/dev/null || true"),
            ("Purge memory", "purge 2>/dev/null || true"),
            ("Restart Dock", "killall Dock"),
        ]

        def run():
            self._write_to(
                self.maint_terminal,
                "=== MAINTENANCE CYCLE STARTED ===",
                "accent",  # noqa: E501
            )
            for i, (desc, cmd) in enumerate(steps, 1):
                self._write_to(
                    self.maint_terminal,
                    f"[{i}/{len(steps)}] {desc}...",
                    "command",  # noqa: E501
                )
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
                    self._write_to(
                        self.maint_terminal, f"    ✓ {desc} complete", "accent"
                    )
                except Exception as e:
                    self._write_to(
                        self.maint_terminal,
                        f"    ✗ {desc} failed: {e}",
                        "error",  # noqa: E501
                    )
                time.sleep(0.5)

            self._write_to(
                self.maint_terminal,
                "=== MAINTENANCE CYCLE COMPLETE ===",
                "accent",  # noqa: E501
            )
            self.status_label.config(text="READY")

        self.status_label.config(text="MAINTENANCE RUNNING")
        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _check_memory_pressure(self):
        """Check and display memory pressure"""

        def run():
            try:
                mem = psutil.virtual_memory()
                pct = mem.percent
                avail_gb = mem.available / (1024**3)
                total_gb = mem.total / (1024**3)

                bar_len = 30
                filled = int(bar_len * pct / 100)
                bar = "█" * filled + "░" * (bar_len - filled)

                if pct > 90:
                    level, tag = "CRITICAL", "error"
                elif pct > 75:
                    level, tag = "WARNING", "warning"
                else:
                    level, tag = "NOMINAL", "accent"

                self._write_to(
                    self.maint_terminal, f"Memory Pressure: {level}", tag
                )  # noqa: E501
                self._write_to(
                    self.maint_terminal, f"  [{bar}] {pct:.1f}%", tag
                )  # noqa: E501
                self._write_to(
                    self.maint_terminal,
                    f"  Available: {avail_gb:.1f}GB / " f"{total_gb:.1f}GB",
                    tag,
                )
            except Exception as e:
                self._write_to(
                    self.maint_terminal, f"Error checking memory: {e}", "error"
                )

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _view_config(self):
        """Display current configuration"""
        config = self.config_manager.load()
        self._write_to(self.maint_terminal, "=== CURRENT CONFIGURATION ===", "accent")
        config_str = json.dumps(config, indent=2)
        for line in config_str.split("\n"):
            self._write_to(self.maint_terminal, f"  {line}", "command")

    def _load_protected_list(self):
        """Load protected processes into listbox"""
        config = self.config_manager.load()
        procs = config.get("protectedProcesses", [])
        self.prot_listbox.delete(0, tk.END)
        for p in procs:
            self.prot_listbox.insert(tk.END, p)

    def _add_protected(self):
        """Add process to protected list"""
        name = self.prot_entry.get().strip()
        if not name:
            return
        self.config_manager.add_protected(name)
        self.prot_entry.delete(0, tk.END)
        self._load_protected_list()
        self._write_to(
            self.maint_terminal, f"Added '{name}' to protected list", "accent"
        )

    def _remove_protected(self):
        """Remove selected process from protected list"""
        sel = self.prot_listbox.curselection()
        if not sel:
            return
        name = self.prot_listbox.get(sel[0])
        self.config_manager.remove_protected(name)
        self._load_protected_list()
        self._write_to(
            self.maint_terminal,
            f"Removed '{name}' from protected list",
            "warning",  # noqa: E501
        )

    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal_output.config(state="normal")
        self.terminal_output.delete(1.0, "end")
        self.terminal_output.config(state="disabled")
        self.write_output("Terminal cleared", "accent")

    def quit_app(self):
        """Quit application"""
        self.monitoring = False
        self.stress_testing = False
        self.write_output("Shutting down GerdsenAI OptiMac...", "warning")
        self.root.after(1000, self.root.quit)

    def start_queue_processor(self):
        """Start queue processor for thread communication"""
        self.process_queue()

    def process_queue(self):
        """Process messages from background threads"""
        try:
            while True:
                msg_type, msg_data = self.output_queue.get_nowait()

                if msg_type == "monitor_display":
                    self.display_monitor_stats(msg_data)
                elif msg_type == "monitor_error":
                    self.write_output(f"Monitor error: {msg_data}", "error")
                elif msg_type == "stress_update":
                    self._write_to(self.test_terminal, msg_data, "warning")
                elif msg_type == "stress_complete":
                    self._write_to(self.test_terminal, msg_data, "accent")
                    self.status_label.config(text="READY")
                elif msg_type == "stress_error":
                    self._write_to(self.test_terminal, msg_data, "error")
                    self.status_label.config(text="ERROR")
                elif msg_type == "optimize_step":
                    description, cmd = msg_data
                    self._write_to(self.opt_terminal, f">> {description}", "command")
                    self.command_executor.execute_command(cmd, description)
                elif msg_type == "optimize_complete":
                    self._write_to(self.opt_terminal, msg_data, "accent")
                    self.status_label.config(text="READY")

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)


def main():
    """Main entry point"""
    # Check platform compatibility
    if platform.system() != "Darwin":
        print("ERROR: This tool is designed for macOS only.")
        sys.exit(1)

    # Check for required Python modules
    try:
        import psutil  # noqa: F401
    except ImportError:
        print("ERROR: psutil module required." " Install with: pip install psutil")
        sys.exit(1)

    # Create and run application
    root = tk.Tk()
    GerdsenAIOptiMac(root)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)


if __name__ == "__main__":
    main()
