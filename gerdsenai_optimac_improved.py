#!/usr/bin/env python3
"""
GerdsenAI OptiMac v2.1 - Improved Mac Performance Optimizer
Enhanced performance monitoring and optimization for Apple Silicon Macs
Settings-enabled GUI with MCP server config unification
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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


def get_compressed_memory_bytes():
    """Get compressed memory from vm_stat (psutil misses this on macOS)."""
    try:
        output = subprocess.check_output(["vm_stat"], text=True)
        page_size = 16384  # Apple Silicon default
        m = re.search(r"page size of (\d+) bytes", output)
        if m:
            page_size = int(m.group(1))
        m = re.search(r"Pages occupied by compressor:\s+(\d+)", output)
        if m:
            return int(m.group(1)) * page_size
    except Exception:
        pass
    return 0


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
                gpu_result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                gpu_cores_detected = False
                if "Total Number of Cores" in gpu_result.stdout:
                    match = re.search(
                        r"Total Number of Cores:\s*(\d+)", gpu_result.stdout
                    )
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True
                if not gpu_cores_detected and "GPU Cores" in gpu_result.stdout:
                    match = re.search(r"GPU Cores:\s*(\d+)", gpu_result.stdout)
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True
                if not gpu_cores_detected and "Metal" in gpu_result.stdout:
                    metal_match = re.search(
                        r"(\d+)\s*(?:GPU\s*)?[Cc]ores?", gpu_result.stdout
                    )
                    if metal_match:
                        info["gpu_cores"] = int(metal_match.group(1))
            except (subprocess.SubprocessError, ValueError, OSError):
                info["cpu_cores"] = os.cpu_count() or 8
        except Exception as e:
            print(f"Chip detection error: {e}")
        return info

    def get_chip_capabilities(self, model):
        """Get known capabilities for specific chip models"""
        capabilities = {
            "M1": {"gpu_cores": 7, "memory_bandwidth": 68.25, "neural_tops": 11},
            "M1 Pro": {"gpu_cores": 14, "memory_bandwidth": 200, "neural_tops": 11},
            "M1 Max": {"gpu_cores": 24, "memory_bandwidth": 400, "neural_tops": 11},
            "M1 Ultra": {"gpu_cores": 48, "memory_bandwidth": 800, "neural_tops": 22},
            "M2": {"gpu_cores": 8, "memory_bandwidth": 100, "neural_tops": 15.8},
            "M2 Pro": {"gpu_cores": 16, "memory_bandwidth": 200, "neural_tops": 15.8},
            "M2 Max": {"gpu_cores": 30, "memory_bandwidth": 400, "neural_tops": 15.8},
            "M2 Ultra": {
                "gpu_cores": 60,
                "memory_bandwidth": 800,
                "neural_tops": 31.6,
            },
            "M3": {"gpu_cores": 8, "memory_bandwidth": 100, "neural_tops": 18},
            "M3 Pro": {"gpu_cores": 14, "memory_bandwidth": 150, "neural_tops": 18},
            "M3 Max": {"gpu_cores": 30, "memory_bandwidth": 400, "neural_tops": 18},
            "M4": {"gpu_cores": 8, "memory_bandwidth": 120, "neural_tops": 38},
            "M4 Pro": {"gpu_cores": 16, "memory_bandwidth": 273, "neural_tops": 38},
            "M4 Max": {"gpu_cores": 32, "memory_bandwidth": 546, "neural_tops": 38},
        }
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
                    match = re.search(
                        r"Total Number of Cores:\s*(\d+)", result.stdout
                    )
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
        interfaces = psutil.net_if_stats()
        for name, stats in interfaces.items():
            if stats.isup and not name.startswith("lo"):
                return name
        return "en0"

    def get_network_stats(self):
        """Get current network statistics"""
        try:
            current_time = time.time()
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
            n = 982451653
            all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1))
            sum(
                math.sin(i) * math.cos(i) * math.sqrt(i + 1) for i in range(1000)
            )
            if operations % 10 == 0:
                a = [[random.random() for _ in range(50)] for _ in range(50)]
                b = [[random.random() for _ in range(50)] for _ in range(50)]
                [
                    [
                        sum(a[i][k] * b[k][j] for k in range(50)) for j in range(25)
                    ]
                    for i in range(25)
                ]
            running = not stop_event.is_set()
            operations += 1
            if operations % 100 == 0:
                time.sleep(0.001)
        return operations

    def memory_stress_worker(self, target_mb):
        """Memory allocation stress"""
        allocated_blocks = []
        block_size = 1024 * 1024
        try:
            for i in range(target_mb):
                block = bytearray(block_size)
                for j in range(0, block_size, 4096):
                    block[j : j + 8] = (i * j).to_bytes(8, "little")
                allocated_blocks.append(block)
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
            subprocess.run(
                ["lms", "server", "stop"], capture_output=True, timeout=5
            )
            return "LM Studio server stopped"
        elif service_name == "mlx":
            subprocess.run(
                ["pkill", "-f", "mlx_lm.server"],
                capture_output=True,
                timeout=5,
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

    def serve_model_ollama(self, model_name):
        """Start serving a model with Ollama (ollama run in background)."""
        try:
            # Ensure server is running first
            if not self.check_port(self.SERVICES["ollama"]["port"]):
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                import time
                time.sleep(2)
            # Run the model (loads it into memory for serving)
            proc = subprocess.Popen(
                ["ollama", "run", model_name, "--keepalive", "0"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Send empty input to just load the model, then close stdin
            proc.stdin.write("/bye\n")
            proc.stdin.flush()
            proc.stdin.close()
            return proc
        except (OSError, FileNotFoundError):
            return None

    def serve_model_mlx(self, model_path_or_id, port=8080):
        """Start MLX server with a specific model."""
        try:
            proc = subprocess.Popen(
                ["python3", "-m", "mlx_lm.server",
                 "--model", model_path_or_id,
                 "--port", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return proc
        except (OSError, FileNotFoundError):
            return None

    def get_ollama_running_models(self):
        """List currently loaded/running models in Ollama."""
        try:
            result = subprocess.run(
                ["ollama", "ps"], capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() if result.stdout else "No models running"
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return "Ollama not available"

    def update_ports(self, ports_dict):
        """Update service port configuration"""
        for svc, port in ports_dict.items():
            if svc in self.SERVICES:
                self.SERVICES[svc]["port"] = port


class ConfigManager:
    """Manage OptiMac configuration at ~/.optimac/config.json
    Unified format shared with the OptiMac MCP server."""

    DEFAULT_CONFIG = {
        "protectedProcesses": [
            "ollama",
            "lmstudio",
            "LM Studio",
            "mlx",
            "python3",
            "python",
            "node",
            "claude",
            "openclaw",
            "sshd",
            "WindowServer",
            "loginwindow",
            "launchd",
            "kernel_task",
            "mds_stores",
            "coreaudiod",
            "systemsoundserverd",
        ],
        "memoryWarningThreshold": 0.75,
        "memoryCriticalThreshold": 0.90,
        "autoKillAtCritical": True,
        "maxProcessRSSMB": 2048,
        "maintenanceIntervalSec": 21600,
        "dnsServers": ["1.1.1.1", "1.0.0.1"],
        "spotlightExclusions": [
            "~/.ollama",
            "~/models",
            "~/.cache",
            "~/Library/Caches",
        ],
        "disabledServices": [],
        "aiStackPorts": {"ollama": 11434, "lmstudio": 1234, "mlx": 8080},
        "modelBaseDir": "",
    }

    DEBLOAT_SERVICES = {
        "minimal": [
            "com.apple.Siri.agent",
            "com.apple.notificationcenterui.agent",
            "com.apple.bird",
        ],
        "moderate": [
            "com.apple.Siri.agent",
            "com.apple.notificationcenterui.agent",
            "com.apple.bird",
            "com.apple.photoanalysisd",
            "com.apple.mediaanalysisd",
            "com.apple.suggestd",
            "com.apple.assistantd",
            "com.apple.parsec-fbf",
            "com.apple.knowledge-agent",
            "com.apple.AirPlayXPCHelper",
        ],
        "aggressive": [
            "com.apple.Siri.agent",
            "com.apple.notificationcenterui.agent",
            "com.apple.bird",
            "com.apple.photoanalysisd",
            "com.apple.mediaanalysisd",
            "com.apple.suggestd",
            "com.apple.assistantd",
            "com.apple.parsec-fbf",
            "com.apple.knowledge-agent",
            "com.apple.AirPlayXPCHelper",
            "com.apple.locationd",
            "com.apple.commerce",
            "com.apple.tipsd",
            "com.apple.routined",
            "com.apple.screensharing",
        ],
    }

    def __init__(self):
        self.config_dir = Path.home() / ".optimac"
        self.config_file = self.config_dir / "config.json"

    def load(self):
        """Load config, merging with defaults for any missing keys"""
        config = dict(self.DEFAULT_CONFIG)
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    saved = json.load(f)
                config.update(saved)
            except (json.JSONDecodeError, OSError):
                pass
        return config

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

    def reset_to_defaults(self):
        """Reset config to defaults"""
        self.save(dict(self.DEFAULT_CONFIG))
        return dict(self.DEFAULT_CONFIG)


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
                output_lines = result.stdout.strip().split("\n")
                if len(output_lines) > 10:
                    self.terminal.write_output(
                        f"Output: {len(output_lines)} lines processed", "success"
                    )
                else:
                    self.terminal.write_output(result.stdout.strip(), "success")
            if result.stderr:
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
                self.terminal.write_output("Command completed successfully", "success")
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.terminal.write_output("Command timed out", "error")
            return False
        except Exception as e:
            self.terminal.write_output(f"Error: {str(e)}", "error")
            return False


class GerdsenAIOptiMac:
    VERSION = "2.3"

    def __init__(self, root):
        self.root = root
        self.root.title(f"GerdsenAI OptiMac v{self.VERSION} - Terminal Edition")
        self.root.geometry("1200x880")
        self.root.configure(bg="#000000")
        self.root.minsize(900, 700)

        # Retro terminal colors
        self.bg_color = "#000000"
        self.fg_color = "#00FF00"
        self.accent_color = "#00FF66"
        self.warning_color = "#FFFF00"
        self.error_color = "#FF0000"
        self.command_color = "#00FFFF"
        self.dim_color = "#006600"

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
        self._config_dirty = False
        self.has_sudo = False

        # Load config and apply to AI manager
        self._current_config = self.config_manager.load()
        ports = self._current_config.get("aiStackPorts", {})
        self.ai_manager.update_ports(ports)

        # Create GUI
        self.configure_styles()
        self.create_interface()
        self.start_queue_processor()

        # Check sudo status
        self.check_sudo_status()

        # Keyboard shortcuts
        self.root.bind("<Control-q>", lambda e: self.quit_app())
        self.root.bind("<Control-m>", lambda e: self.toggle_monitoring())
        self.root.bind("<Control-s>", lambda e: self._save_settings())

    def configure_styles(self):
        """Configure ttk styles for dark retro theme"""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=self.bg_color, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background="#001a00",
            foreground=self.fg_color,
            padding=[12, 5],
            font=("Courier New", 9, "bold"),
            borderwidth=1,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", "#003300"), ("active", "#002200")],
            foreground=[("selected", self.accent_color), ("active", self.fg_color)],
        )

    def create_interface(self):
        """Create retro terminal interface with tabs"""
        self.create_banner()
        self.create_system_info()

        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10)

        self.create_dashboard_tab()
        self.create_tests_tab()
        self.create_optimize_tab()
        self.create_ai_tab()
        self.create_maintenance_tab()
        self.create_settings_tab()

        self.create_status_bar()

    def create_banner(self):
        """Create compact banner"""
        banner_frame = tk.Frame(self.root, bg=self.bg_color)
        banner_frame.pack(fill="x", padx=10, pady=(5, 2))
        banner_text = (
            f" GERDSENAI  O P T I M A C  v{self.VERSION}"
            "   |   Apple Silicon Performance Optimizer"
        )
        tk.Label(
            banner_frame,
            text=banner_text,
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Courier New", 11, "bold"),
            justify="left",
        ).pack(anchor="w")

    def create_system_info(self):
        """Create system information display"""
        info_frame = tk.Frame(self.root, bg=self.bg_color)
        info_frame.pack(fill="x", padx=10, pady=(0, 5))
        chip = self.silicon_monitor.chip_info
        mem_gb = psutil.virtual_memory().total / (1024 ** 3)
        info_text = (
            f"SYSTEM: Apple {chip['model']} | "
            f"CPU: {chip.get('perf_cores', '?')}P+"
            f"{chip.get('eff_cores', '?')}E cores | "
            f"GPU: {chip.get('gpu_cores', '?')} cores | "
            f"NPU: {chip['neural_cores']} cores "
            f"({chip.get('neural_tops', '?')} TOPS) | "
            f"RAM: {mem_gb:.0f}GB"
        )
        tk.Label(
            info_frame,
            text=info_text,
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
        ).pack(anchor="w")

    def _make_btn(self, parent, text, command, width=None):
        """Create a Label-based button for full color control on macOS.
        tk.Button on macOS Aqua reverts to white system appearance;
        tk.Label with click bindings avoids this entirely."""
        rest_bg = "#001a00"
        hover_bg = "#002200"
        click_bg = "#003300"  # matches selected tab color

        # Outer frame provides the border
        border = tk.Frame(parent, bg="#004400", bd=0)
        lbl = tk.Label(
            border, text=text, bg=rest_bg, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
            padx=12, pady=4, cursor="hand2",
        )
        if width:
            lbl.config(width=width)
        lbl.pack(padx=1, pady=1)

        def on_enter(e):
            lbl.config(bg=hover_bg)

        def on_leave(e):
            lbl.config(bg=rest_bg)

        def on_press(e):
            lbl.config(bg=click_bg, fg=self.accent_color)

        def on_release(e):
            lbl.config(fg=self.fg_color)
            lbl.after(120, lambda: lbl.config(bg=rest_bg))
            command()

        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<ButtonPress-1>", on_press)
        lbl.bind("<ButtonRelease-1>", on_release)

        # Return the border frame so .pack() works on it
        border._inner_label = lbl  # keep reference
        return border

    def _make_tab_frame(self, title):
        frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(frame, text=f" {title} ")
        return frame

    def _make_tab_terminal(self, parent, height=12):
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
            ("dim", self.dim_color),
        ]:
            term.tag_config(tag, foreground=color)
        return term

    def _write_to(self, terminal, text, tag="success"):
        ts = datetime.now().strftime("%H:%M:%S")
        terminal.config(state="normal")
        terminal.insert("end", f"[{ts}] {text}\n", tag)
        terminal.see("end")
        terminal.config(state="disabled")

    def _make_label_frame(self, parent, title):
        return tk.LabelFrame(
            parent,
            text=f" {title} ",
            bg=self.bg_color,
            fg=self.accent_color,
            font=("Courier New", 9, "bold"),
            padx=5,
            pady=3,
        )

    # ================================================================
    # Tab 1: Dashboard
    # ================================================================
    def create_dashboard_tab(self):
        tab = self._make_tab_frame("DASHBOARD")
        ctrl = tk.Frame(tab, bg=self.bg_color)
        ctrl.pack(fill="x", padx=5, pady=5)
        self._make_btn(ctrl, "START MONITOR", self.toggle_monitoring).pack(
            side="left", padx=3
        )
        self._make_btn(ctrl, "CLEAR", self.clear_terminal).pack(side="left", padx=3)
        self._make_btn(ctrl, "EXIT", self.quit_app).pack(side="right", padx=3)

        self.terminal_output = self._make_tab_terminal(tab, height=20)
        self.terminal_output.pack(fill="both", expand=True, padx=5, pady=5)
        self.command_executor = CommandExecutor(self)
        self.write_output(
            f"GerdsenAI OptiMac Terminal v{self.VERSION} Initialized", "accent"
        )
        self.write_output("Ready for optimization and monitoring", "success")
        self.write_output(
            "Shortcuts: Ctrl+M monitor | Ctrl+S save settings | Ctrl+Q quit", "dim"
        )

    # ================================================================
    # Tab 2: Stress Tests
    # ================================================================
    def create_tests_tab(self):
        tab = self._make_tab_frame("STRESS TESTS")
        dur_frame = tk.Frame(tab, bg=self.bg_color)
        dur_frame.pack(fill="x", padx=5, pady=5)
        tk.Label(
            dur_frame, text="DURATION:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)
        self.duration_var = tk.StringVar(value="30s")
        for val in ["10s", "30s", "60s", "120s"]:
            tk.Radiobutton(
                dur_frame, text=val, variable=self.duration_var, value=val,
                bg=self.bg_color, fg=self.fg_color, selectcolor="#003300",
                activebackground=self.bg_color, activeforeground=self.accent_color,
                font=("Courier New", 10), command=self._update_duration,
            ).pack(side="left", padx=5)
        btn_frame = tk.Frame(tab, bg=self.bg_color)
        btn_frame.pack(fill="x", padx=5, pady=5)
        for text, cmd in [
            ("CPU TEST", self.run_cpu_stress),
            ("MEMORY TEST", self.run_memory_stress),
            ("COMBINED TEST", self.run_combined_stress),
        ]:
            self._make_btn(btn_frame, text, cmd).pack(side="left", padx=3)
        self.test_terminal = self._make_tab_terminal(tab, height=18)
        self.test_terminal.pack(fill="both", expand=True, padx=5, pady=5)

    def _update_duration(self):
        self.stress_duration = int(self.duration_var.get().rstrip("s"))

    # ================================================================
    # Tab 3: Optimize
    # ================================================================
    def create_optimize_tab(self):
        tab = self._make_tab_frame("OPTIMIZE")
        qa_frame = self._make_label_frame(tab, "Quick Actions")
        qa_frame.pack(fill="x", padx=5, pady=3)
        for text, cmd in [
            ("PURGE MEM", self._purge_memory),
            ("FLUSH DNS", self._flush_dns),
            ("FLUSH ROUTES", self._flush_routes),
            ("CLEAR CACHES", self._clear_caches),
        ]:
            self._make_btn(qa_frame, text, cmd).pack(side="left", padx=3, pady=3)

        pwr_frame = self._make_label_frame(tab, "Power Profile")
        pwr_frame.pack(fill="x", padx=5, pady=3)
        self.power_var = tk.StringVar(value="default")
        for val, label in [
            ("default", "Default"),
            ("ai_server", "AI Server"),
            ("low_power", "Low Power"),
        ]:
            tk.Radiobutton(
                pwr_frame, text=label, variable=self.power_var, value=val,
                bg=self.bg_color, fg=self.fg_color, selectcolor="#003300",
                activebackground=self.bg_color, activeforeground=self.accent_color,
                font=("Courier New", 10),
            ).pack(side="left", padx=5, pady=3)
        self._make_btn(pwr_frame, "APPLY", self._apply_power_profile).pack(
            side="left", padx=10, pady=3
        )

        misc_frame = tk.Frame(tab, bg=self.bg_color)
        misc_frame.pack(fill="x", padx=5, pady=3)
        self._make_btn(
            misc_frame, "DISABLE SPOTLIGHT",
            lambda: self._run_opt_cmd("sudo mdutil -a -i off", "Disabling Spotlight"),
        ).pack(side="left", padx=3)
        self._make_btn(
            misc_frame, "ENABLE SPOTLIGHT",
            lambda: self._run_opt_cmd("sudo mdutil -a -i on", "Enabling Spotlight"),
        ).pack(side="left", padx=3)
        self._make_btn(
            misc_frame, "SET DNS CF",
            lambda: self._run_opt_cmd(
                "networksetup -setdnsservers Wi-Fi 1.1.1.1 1.0.0.1",
                "Setting DNS to Cloudflare",
            ),
        ).pack(side="left", padx=3)
        self._make_btn(
            misc_frame, "REDUCE UI", self._reduce_ui_overhead,
        ).pack(side="left", padx=3)

        self._make_btn(tab, "RUN FULL OPTIMIZE", self.run_optimization).pack(
            padx=5, pady=3, anchor="w"
        )
        self.opt_terminal = self._make_tab_terminal(tab, height=14)
        self.opt_terminal.pack(fill="both", expand=True, padx=5, pady=5)

    # ================================================================
    # Tab 4: AI Stack
    # ================================================================
    def create_ai_tab(self):
        tab = self._make_tab_frame("AI STACK")
        status_frame = self._make_label_frame(tab, "Service Status")
        status_frame.pack(fill="x", padx=5, pady=3)
        self.ai_status_labels = {}
        for svc in ["ollama", "lmstudio", "mlx"]:
            row = tk.Frame(status_frame, bg=self.bg_color)
            row.pack(fill="x", padx=5, pady=2)
            tk.Label(
                row, text=f"{svc.upper()}:", bg=self.bg_color, fg=self.fg_color,
                font=("Courier New", 10, "bold"), width=12, anchor="w",
            ).pack(side="left")
            lbl = tk.Label(
                row, text="checking...", bg=self.bg_color, fg=self.warning_color,
                font=("Courier New", 10), width=18, anchor="w",
            )
            lbl.pack(side="left", padx=5)
            self.ai_status_labels[svc] = lbl
            self._make_btn(row, "START", lambda s=svc: self._ai_start(s)).pack(
                side="left", padx=2
            )
            self._make_btn(row, "STOP", lambda s=svc: self._ai_stop(s)).pack(
                side="left", padx=2
            )

        ctrl_frame = tk.Frame(tab, bg=self.bg_color)
        ctrl_frame.pack(fill="x", padx=5, pady=3)
        self._make_btn(ctrl_frame, "REFRESH STATUS", self._refresh_ai_status).pack(
            side="left", padx=3
        )
        self._make_btn(ctrl_frame, "LIST MODELS", self._list_models).pack(
            side="left", padx=3
        )
        self._make_btn(ctrl_frame, "BROWSE MODELS", self._browse_models).pack(
            side="left", padx=3
        )

        # Model directory
        dir_frame = self._make_label_frame(tab, "Model Directory")
        dir_frame.pack(fill="x", padx=5, pady=3)
        dir_row = tk.Frame(dir_frame, bg=self.bg_color)
        dir_row.pack(fill="x", padx=5, pady=3)
        tk.Label(
            dir_row, text="BASE DIR:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)
        self.model_dir_var = tk.StringVar(
            value=self._current_config.get("modelBaseDir", "")
        )
        self.model_dir_entry = tk.Entry(
            dir_row, textvariable=self.model_dir_var,
            bg="#001100", fg=self.fg_color,
            insertbackground=self.fg_color, font=("Courier New", 10), width=40,
        )
        self.model_dir_entry.pack(side="left", padx=3, fill="x", expand=True)
        self._make_btn(dir_row, "BROWSE", self._browse_model_dir).pack(
            side="left", padx=3
        )
        self._make_btn(dir_row, "SAVE", self._save_model_dir).pack(
            side="left", padx=3
        )

        # Pull model
        pull_frame = tk.Frame(tab, bg=self.bg_color)
        pull_frame.pack(fill="x", padx=5, pady=3)
        tk.Label(
            pull_frame, text="PULL MODEL:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)
        self.model_entry = tk.Entry(
            pull_frame, bg="#001100", fg=self.fg_color,
            insertbackground=self.fg_color, font=("Courier New", 10), width=30,
        )
        self.model_entry.pack(side="left", padx=3)
        self._make_btn(pull_frame, "PULL", self._pull_model).pack(side="left", padx=3)

        # Model Serving section
        serve_frame = self._make_label_frame(tab, "Serve / Host Model")
        serve_frame.pack(fill="x", padx=5, pady=3)

        serve_row1 = tk.Frame(serve_frame, bg=self.bg_color)
        serve_row1.pack(fill="x", padx=5, pady=2)
        tk.Label(
            serve_row1, text="MODEL:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)
        self.serve_model_var = tk.StringVar()
        self.serve_model_entry = tk.Entry(
            serve_row1, textvariable=self.serve_model_var,
            bg="#001100", fg=self.fg_color,
            insertbackground=self.fg_color, font=("Courier New", 10), width=35,
        )
        self.serve_model_entry.pack(side="left", padx=3, fill="x", expand=True)
        self._make_btn(serve_row1, "PICK FILE", self._pick_model_file).pack(
            side="left", padx=2
        )

        serve_row2 = tk.Frame(serve_frame, bg=self.bg_color)
        serve_row2.pack(fill="x", padx=5, pady=2)
        tk.Label(
            serve_row2, text="RUNTIME:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        ).pack(side="left", padx=3)
        self.serve_runtime_var = tk.StringVar(value="ollama")
        for val, label in [("ollama", "Ollama"), ("mlx", "MLX")]:
            tk.Radiobutton(
                serve_row2, text=label, variable=self.serve_runtime_var, value=val,
                bg=self.bg_color, fg=self.fg_color, selectcolor="#003300",
                activebackground=self.bg_color, activeforeground=self.accent_color,
                font=("Courier New", 10),
            ).pack(side="left", padx=4)
        self._make_btn(serve_row2, "SERVE MODEL", self._serve_model).pack(
            side="left", padx=8
        )
        self._make_btn(serve_row2, "RUNNING MODELS", self._show_running_models).pack(
            side="left", padx=3
        )

        self.ai_terminal = self._make_tab_terminal(tab, height=10)
        self.ai_terminal.pack(fill="both", expand=True, padx=5, pady=5)
        self.root.after(500, self._refresh_ai_status)

    # ================================================================
    # Tab 5: Maintenance
    # ================================================================
    def create_maintenance_tab(self):
        tab = self._make_tab_frame("MAINTENANCE")
        maint_frame = self._make_label_frame(tab, "Maintenance")
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
        prot_frame = self._make_label_frame(tab, "Protected Processes")
        prot_frame.pack(fill="x", padx=5, pady=3)
        list_frame = tk.Frame(prot_frame, bg=self.bg_color)
        list_frame.pack(fill="x", padx=5, pady=3)
        self.prot_listbox = tk.Listbox(
            list_frame, bg="#001100", fg=self.fg_color,
            font=("Courier New", 10), height=4, selectbackground="#003300",
        )
        self.prot_listbox.pack(side="left", fill="x", expand=True)
        btn_col = tk.Frame(list_frame, bg=self.bg_color)
        btn_col.pack(side="left", padx=5)
        self._make_btn(btn_col, "ADD", self._add_protected).pack(pady=2)
        self._make_btn(btn_col, "REMOVE", self._remove_protected).pack(pady=2)
        add_frame = tk.Frame(prot_frame, bg=self.bg_color)
        add_frame.pack(fill="x", padx=5, pady=3)
        self.prot_entry = tk.Entry(
            add_frame, bg="#001100", fg=self.fg_color,
            insertbackground=self.fg_color, font=("Courier New", 10), width=30,
        )
        self.prot_entry.pack(side="left", padx=3)
        self.maint_terminal = self._make_tab_terminal(tab, height=12)
        self.maint_terminal.pack(fill="both", expand=True, padx=5, pady=5)
        self._load_protected_list()

    # ================================================================
    # Tab 6: SETTINGS
    # ================================================================
    def create_settings_tab(self):
        """Settings tab - all configurable options in one place.
        Reads/writes ~/.optimac/config.json (shared with MCP server)."""
        tab = self._make_tab_frame("SETTINGS")

        # Scrollable container
        canvas = tk.Canvas(tab, bg=self.bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview, bg="#002200")
        scroll_frame = tk.Frame(canvas, bg=self.bg_color)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        config = self._current_config

        # -- Memory Management --
        mem_frame = self._make_label_frame(scroll_frame, "Memory Management")
        mem_frame.pack(fill="x", padx=5, pady=4)

        row = tk.Frame(mem_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(
            row, text="Warning Threshold:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10), width=22, anchor="w",
        ).pack(side="left")
        self.warn_threshold_var = tk.IntVar(
            value=int(config.get("memoryWarningThreshold", 0.75) * 100)
        )
        tk.Scale(
            row, from_=50, to=95, orient="horizontal",
            variable=self.warn_threshold_var,
            bg=self.bg_color, fg=self.fg_color, troughcolor="#002200",
            highlightbackground=self.bg_color, font=("Courier New", 9),
            length=200, command=lambda v: self._mark_dirty(),
        ).pack(side="left", padx=5)
        tk.Label(row, text="%", bg=self.bg_color, fg=self.dim_color,
                 font=("Courier New", 10)).pack(side="left")

        row = tk.Frame(mem_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(
            row, text="Critical Threshold:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10), width=22, anchor="w",
        ).pack(side="left")
        self.crit_threshold_var = tk.IntVar(
            value=int(config.get("memoryCriticalThreshold", 0.90) * 100)
        )
        tk.Scale(
            row, from_=60, to=99, orient="horizontal",
            variable=self.crit_threshold_var,
            bg=self.bg_color, fg=self.fg_color, troughcolor="#002200",
            highlightbackground=self.bg_color, font=("Courier New", 9),
            length=200, command=lambda v: self._mark_dirty(),
        ).pack(side="left", padx=5)
        tk.Label(row, text="%", bg=self.bg_color, fg=self.dim_color,
                 font=("Courier New", 10)).pack(side="left")

        row = tk.Frame(mem_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        self.autokill_var = tk.BooleanVar(value=config.get("autoKillAtCritical", True))
        tk.Checkbutton(
            row, text="Auto-kill non-protected processes at critical pressure",
            variable=self.autokill_var,
            bg=self.bg_color, fg=self.fg_color, selectcolor="#003300",
            activebackground=self.bg_color, activeforeground=self.accent_color,
            font=("Courier New", 10), command=self._mark_dirty,
        ).pack(side="left", padx=5)

        row = tk.Frame(mem_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(
            row, text="Max Process RSS (MB):", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10), width=22, anchor="w",
        ).pack(side="left")
        self.max_rss_var = tk.StringVar(value=str(config.get("maxProcessRSSMB", 2048)))
        rss_entry = tk.Entry(
            row, textvariable=self.max_rss_var,
            bg="#001100", fg=self.fg_color, insertbackground=self.fg_color,
            font=("Courier New", 10), width=8,
        )
        rss_entry.pack(side="left", padx=5)
        rss_entry.bind("<KeyRelease>", lambda e: self._mark_dirty())
        tk.Label(row, text="(512-16384)", bg=self.bg_color, fg=self.dim_color,
                 font=("Courier New", 9)).pack(side="left")

        # -- Maintenance --
        maint_s_frame = self._make_label_frame(scroll_frame, "Maintenance")
        maint_s_frame.pack(fill="x", padx=5, pady=4)
        row = tk.Frame(maint_s_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(
            row, text="Interval:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10), width=22, anchor="w",
        ).pack(side="left")
        self.maint_interval_var = tk.StringVar()
        interval_options = {
            "30 min": 1800, "1 hour": 3600, "2 hours": 7200,
            "6 hours": 21600, "12 hours": 43200, "24 hours": 86400,
        }
        self._interval_map = interval_options
        current_sec = config.get("maintenanceIntervalSec", 21600)
        current_label = "6 hours"
        for label, sec in interval_options.items():
            if sec == current_sec:
                current_label = label
                break
        self.maint_interval_var.set(current_label)
        interval_menu = tk.OptionMenu(
            row, self.maint_interval_var, *interval_options.keys(),
            command=lambda v: self._mark_dirty(),
        )
        interval_menu.config(
            bg="#002200", fg=self.fg_color, font=("Courier New", 10),
            activebackground="#004400", activeforeground=self.accent_color,
            highlightthickness=0,
        )
        interval_menu["menu"].config(
            bg="#001100", fg=self.fg_color, font=("Courier New", 10),
            activebackground="#003300",
        )
        interval_menu.pack(side="left", padx=5)

        # -- DNS --
        dns_frame = self._make_label_frame(scroll_frame, "DNS Configuration")
        dns_frame.pack(fill="x", padx=5, pady=4)
        row = tk.Frame(dns_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        self.dns_var = tk.StringVar(value="cloudflare")
        current_dns = config.get("dnsServers", ["1.1.1.1", "1.0.0.1"])
        if current_dns == ["8.8.8.8", "8.8.4.4"]:
            self.dns_var.set("google")
        elif current_dns == ["9.9.9.9", "149.112.112.112"]:
            self.dns_var.set("quad9")
        elif current_dns != ["1.1.1.1", "1.0.0.1"]:
            self.dns_var.set("custom")
        for val, label in [
            ("cloudflare", "Cloudflare (1.1.1.1)"),
            ("google", "Google (8.8.8.8)"),
            ("quad9", "Quad9 (9.9.9.9)"),
            ("custom", "Custom"),
        ]:
            tk.Radiobutton(
                row, text=label, variable=self.dns_var, value=val,
                bg=self.bg_color, fg=self.fg_color, selectcolor="#003300",
                activebackground=self.bg_color, activeforeground=self.accent_color,
                font=("Courier New", 10), command=self._mark_dirty,
            ).pack(side="left", padx=4)
        row = tk.Frame(dns_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=2)
        tk.Label(
            row, text="Custom DNS:", bg=self.bg_color, fg=self.fg_color,
            font=("Courier New", 10), width=22, anchor="w",
        ).pack(side="left")
        custom_dns_str = ", ".join(current_dns) if self.dns_var.get() == "custom" else ""
        self.custom_dns_var = tk.StringVar(value=custom_dns_str)
        tk.Entry(
            row, textvariable=self.custom_dns_var,
            bg="#001100", fg=self.fg_color, insertbackground=self.fg_color,
            font=("Courier New", 10), width=30,
        ).pack(side="left", padx=5)
        tk.Label(row, text="(comma separated)", bg=self.bg_color, fg=self.dim_color,
                 font=("Courier New", 9)).pack(side="left")
        self._make_btn(dns_frame, "APPLY DNS NOW", self._apply_dns_now).pack(
            padx=5, pady=3, anchor="w"
        )

        # -- AI Stack Ports --
        ports_frame = self._make_label_frame(scroll_frame, "AI Stack Ports")
        ports_frame.pack(fill="x", padx=5, pady=4)
        self.port_vars = {}
        ports = config.get("aiStackPorts", {})
        for svc, default_port in [("ollama", 11434), ("lmstudio", 1234), ("mlx", 8080)]:
            row = tk.Frame(ports_frame, bg=self.bg_color)
            row.pack(fill="x", padx=5, pady=1)
            tk.Label(
                row, text=f"{svc.upper()} Port:", bg=self.bg_color, fg=self.fg_color,
                font=("Courier New", 10), width=22, anchor="w",
            ).pack(side="left")
            var = tk.StringVar(value=str(ports.get(svc, default_port)))
            self.port_vars[svc] = var
            entry = tk.Entry(
                row, textvariable=var, bg="#001100", fg=self.fg_color,
                insertbackground=self.fg_color, font=("Courier New", 10), width=8,
            )
            entry.pack(side="left", padx=5)
            entry.bind("<KeyRelease>", lambda e: self._mark_dirty())

        # -- Debloat --
        debloat_frame = self._make_label_frame(scroll_frame, "Debloat macOS Services")
        debloat_frame.pack(fill="x", padx=5, pady=4)
        row = tk.Frame(debloat_frame, bg=self.bg_color)
        row.pack(fill="x", padx=5, pady=3)
        tk.Label(row, text="Preset:", bg=self.bg_color, fg=self.fg_color,
                 font=("Courier New", 10)).pack(side="left", padx=3)
        for preset in ["minimal", "moderate", "aggressive"]:
            color = (
                self.fg_color if preset == "minimal"
                else self.warning_color if preset == "moderate"
                else self.error_color
            )
            border = tk.Frame(row, bg="#004400", bd=0)
            lbl = tk.Label(
                border, text=preset.upper(), bg="#002200", fg=color,
                font=("Courier New", 10, "bold"), padx=10, pady=3, cursor="hand2",
            )
            lbl.pack(padx=1, pady=1)
            lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg="#004400"))
            lbl.bind("<Leave>", lambda e, l=lbl: l.config(bg="#002200"))
            lbl.bind("<ButtonPress-1>", lambda e, l=lbl, c=color: l.config(bg="#003300", fg=c))
            lbl.bind("<ButtonRelease-1>", lambda e, l=lbl, p=preset: (
                l.config(bg="#002200"),
                self._apply_debloat(p),
            ))
            border.pack(side="left", padx=4)
        self._make_btn(
            debloat_frame, "RE-ENABLE ALL SERVICES", self._reenable_all_services
        ).pack(padx=5, pady=3, anchor="w")
        tk.Label(
            debloat_frame, text="Currently disabled:", bg=self.bg_color,
            fg=self.dim_color, font=("Courier New", 9),
        ).pack(padx=5, anchor="w")
        self.disabled_svc_listbox = tk.Listbox(
            debloat_frame, bg="#001100", fg=self.warning_color,
            font=("Courier New", 9), height=4, selectbackground="#003300",
        )
        self.disabled_svc_listbox.pack(fill="x", padx=5, pady=2)
        self._refresh_disabled_services()

        # -- Save / Reset --
        btn_row = tk.Frame(scroll_frame, bg=self.bg_color)
        btn_row.pack(fill="x", padx=5, pady=8)
        save_border = tk.Frame(btn_row, bg=self.accent_color, bd=0)
        save_lbl = tk.Label(
            save_border, text="SAVE ALL SETTINGS", bg="#003300",
            fg=self.accent_color, font=("Courier New", 11, "bold"),
            padx=20, pady=6, cursor="hand2",
        )
        save_lbl.pack(padx=1, pady=1)
        save_lbl.bind("<Enter>", lambda e: save_lbl.config(bg="#005500"))
        save_lbl.bind("<Leave>", lambda e: save_lbl.config(bg="#003300"))
        save_lbl.bind("<ButtonPress-1>", lambda e: save_lbl.config(bg="#006600"))
        save_lbl.bind("<ButtonRelease-1>", lambda e: (
            save_lbl.config(bg="#003300"), self._save_settings()
        ))
        save_border.pack(side="left", padx=5)
        self.save_indicator = tk.Label(
            btn_row, text="", bg=self.bg_color, fg=self.accent_color,
            font=("Courier New", 10),
        )
        self.save_indicator.pack(side="left", padx=10)
        reset_border = tk.Frame(btn_row, bg=self.error_color, bd=0)
        reset_lbl = tk.Label(
            reset_border, text="RESET DEFAULTS", bg="#220000",
            fg=self.error_color, font=("Courier New", 10, "bold"),
            padx=10, pady=4, cursor="hand2",
        )
        reset_lbl.pack(padx=1, pady=1)
        reset_lbl.bind("<Enter>", lambda e: reset_lbl.config(bg="#440000"))
        reset_lbl.bind("<Leave>", lambda e: reset_lbl.config(bg="#220000"))
        reset_lbl.bind("<ButtonPress-1>", lambda e: reset_lbl.config(bg="#550000"))
        reset_lbl.bind("<ButtonRelease-1>", lambda e: (
            reset_lbl.config(bg="#220000"), self._reset_settings()
        ))
        reset_border.pack(side="right", padx=5)

        # Settings terminal
        self.settings_terminal = self._make_tab_terminal(scroll_frame, height=6)
        self.settings_terminal.pack(fill="x", padx=5, pady=5)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

    # ================================================================
    # Settings actions
    # ================================================================
    def _mark_dirty(self, *_args):
        self._config_dirty = True
        if hasattr(self, "save_indicator"):
            self.save_indicator.config(text="* unsaved changes", fg=self.warning_color)

    def _save_settings(self):
        config = self._current_config
        config["memoryWarningThreshold"] = self.warn_threshold_var.get() / 100.0
        config["memoryCriticalThreshold"] = self.crit_threshold_var.get() / 100.0
        config["autoKillAtCritical"] = self.autokill_var.get()
        try:
            rss = int(self.max_rss_var.get())
            config["maxProcessRSSMB"] = max(512, min(16384, rss))
        except ValueError:
            pass
        label = self.maint_interval_var.get()
        config["maintenanceIntervalSec"] = self._interval_map.get(label, 21600)
        dns_preset = self.dns_var.get()
        dns_map = {
            "cloudflare": ["1.1.1.1", "1.0.0.1"],
            "google": ["8.8.8.8", "8.8.4.4"],
            "quad9": ["9.9.9.9", "149.112.112.112"],
        }
        if dns_preset in dns_map:
            config["dnsServers"] = dns_map[dns_preset]
        elif dns_preset == "custom":
            raw = self.custom_dns_var.get()
            servers = [s.strip() for s in raw.split(",") if s.strip()]
            if servers:
                config["dnsServers"] = servers
        ports = {}
        for svc, var in self.port_vars.items():
            try:
                ports[svc] = int(var.get())
            except ValueError:
                ports[svc] = self.ai_manager.SERVICES.get(svc, {}).get("port", 0)
        config["aiStackPorts"] = ports
        self.ai_manager.update_ports(ports)
        self.config_manager.save(config)
        self._current_config = config
        self._config_dirty = False
        self.save_indicator.config(text="Saved!", fg=self.accent_color)
        self._write_to(
            self.settings_terminal,
            "Configuration saved to ~/.optimac/config.json", "accent",
        )
        self.root.after(3000, lambda: self.save_indicator.config(text=""))

    def _reset_settings(self):
        if not messagebox.askyesno(
            "Reset Settings", "Reset all settings to defaults? This cannot be undone.",
        ):
            return
        config = self.config_manager.reset_to_defaults()
        self._current_config = config
        self.warn_threshold_var.set(int(config["memoryWarningThreshold"] * 100))
        self.crit_threshold_var.set(int(config["memoryCriticalThreshold"] * 100))
        self.autokill_var.set(config["autoKillAtCritical"])
        self.max_rss_var.set(str(config["maxProcessRSSMB"]))
        self.maint_interval_var.set("6 hours")
        self.dns_var.set("cloudflare")
        self.custom_dns_var.set("")
        for svc, var in self.port_vars.items():
            var.set(str(config["aiStackPorts"].get(svc, 0)))
        self._config_dirty = False
        self.save_indicator.config(text="Reset to defaults", fg=self.warning_color)
        self._write_to(self.settings_terminal, "Settings reset to defaults", "warning")
        self._load_protected_list()
        self._refresh_disabled_services()

    def _apply_dns_now(self):
        dns_preset = self.dns_var.get()
        dns_map = {
            "cloudflare": ["1.1.1.1", "1.0.0.1"],
            "google": ["8.8.8.8", "8.8.4.4"],
            "quad9": ["9.9.9.9", "149.112.112.112"],
        }
        servers = dns_map.get(dns_preset)
        if not servers and dns_preset == "custom":
            raw = self.custom_dns_var.get()
            servers = [s.strip() for s in raw.split(",") if s.strip()]
        if not servers:
            servers = ["1.1.1.1", "1.0.0.1"]
        iface = self.network_monitor.primary_interface or "Wi-Fi"
        cmd = f"networksetup -setdnsservers {iface} {' '.join(servers)}"

        def run():
            self._write_to(
                self.settings_terminal,
                f"Applying DNS: {', '.join(servers)} on {iface}", "command",
            )
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self._write_to(self.settings_terminal, "DNS applied successfully", "accent")
                    subprocess.run("dscacheutil -flushcache", shell=True, timeout=5)
                    self._write_to(self.settings_terminal, "DNS cache flushed", "accent")
                else:
                    self._write_to(
                        self.settings_terminal,
                        f"DNS apply failed: {result.stderr.strip()[:80]}", "error",
                    )
            except Exception as e:
                self._write_to(self.settings_terminal, f"Error: {e}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _apply_debloat(self, preset):
        services = ConfigManager.DEBLOAT_SERVICES.get(preset, [])
        if not services:
            return

        def run():
            self._write_to(
                self.settings_terminal,
                f"Applying {preset.upper()} debloat ({len(services)} services)...",
                "warning",
            )
            uid = str(os.getuid())
            disabled = list(self._current_config.get("disabledServices", []))
            for svc in services:
                try:
                    subprocess.run(
                        ["launchctl", "disable", f"user/{uid}/{svc}"],
                        capture_output=True, timeout=5,
                    )
                    subprocess.run(
                        ["launchctl", "bootout", f"user/{uid}/{svc}"],
                        capture_output=True, timeout=5,
                    )
                    if svc not in disabled:
                        disabled.append(svc)
                    self._write_to(self.settings_terminal, f"  Disabled: {svc}", "accent")
                except Exception as e:
                    self._write_to(self.settings_terminal, f"  Failed: {svc} ({e})", "error")
            self._current_config["disabledServices"] = disabled
            self.config_manager.save(self._current_config)
            self.root.after(0, self._refresh_disabled_services)
            self._write_to(
                self.settings_terminal,
                f"Debloat {preset.upper()} complete - {len(services)} services disabled",
                "accent",
            )

        threading.Thread(target=run, daemon=True).start()

    def _reenable_all_services(self):
        disabled = self._current_config.get("disabledServices", [])
        if not disabled:
            self._write_to(self.settings_terminal, "No disabled services to re-enable", "warning")
            return

        def run():
            uid = str(os.getuid())
            self._write_to(
                self.settings_terminal,
                f"Re-enabling {len(disabled)} services...", "warning",
            )
            for svc in list(disabled):
                try:
                    subprocess.run(
                        ["launchctl", "enable", f"user/{uid}/{svc}"],
                        capture_output=True, timeout=5,
                    )
                    self._write_to(self.settings_terminal, f"  Enabled: {svc}", "accent")
                except Exception as e:
                    self._write_to(self.settings_terminal, f"  Failed: {svc} ({e})", "error")
            self._current_config["disabledServices"] = []
            self.config_manager.save(self._current_config)
            self.root.after(0, self._refresh_disabled_services)
            self._write_to(self.settings_terminal, "All services re-enabled", "accent")

        threading.Thread(target=run, daemon=True).start()

    def _refresh_disabled_services(self):
        self.disabled_svc_listbox.delete(0, tk.END)
        for svc in self._current_config.get("disabledServices", []):
            self.disabled_svc_listbox.insert(tk.END, svc)

    def _reduce_ui_overhead(self):
        cmds = [
            ("Reduce motion", "defaults write com.apple.universalaccess reduceMotion -bool true"),
            ("Reduce transparency", "defaults write com.apple.universalaccess reduceTransparency -bool true"),
            ("Disable animations", "defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false"),
            ("Fast Mission Control", "defaults write com.apple.dock expose-animation-duration -float 0.1"),
            ("Fast Dock hide", "defaults write com.apple.dock autohide-time-modifier -float 0"),
        ]

        def run():
            for desc, cmd in cmds:
                self._write_to(self.opt_terminal, f">> {desc}", "command")
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                    self._write_to(self.opt_terminal, "   OK", "accent")
                except Exception as e:
                    self._write_to(self.opt_terminal, f"   FAIL: {e}", "error")
            subprocess.run("killall Dock", shell=True, capture_output=True, timeout=5)
            self._write_to(self.opt_terminal, "UI overhead reduced - Dock restarted", "accent")

        threading.Thread(target=run, daemon=True).start()

    # ================================================================
    # Status bar
    # ================================================================
    def create_status_bar(self):
        status_frame = tk.Frame(self.root, bg="#001100", height=28)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        self.status_label = tk.Label(
            status_frame, text="READY", bg="#001100", fg=self.fg_color,
            font=("Courier New", 10, "bold"),
        )
        self.status_label.pack(side="left", padx=10, pady=4)
        self.sudo_label = tk.Label(
            status_frame, text="", bg="#001100", fg=self.warning_color,
            font=("Courier New", 10),
        )
        self.sudo_label.pack(side="right", padx=10, pady=4)

    # ================================================================
    # Core operations
    # ================================================================
    def write_output(self, text, tag="success"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.terminal_output.config(state="normal")
        self.terminal_output.insert("end", f"[{ts}] {text}\n", tag)
        self.terminal_output.see("end")
        self.terminal_output.config(state="disabled")

    def check_sudo_status(self):
        """Check if passwordless sudo is available.
        Tests multiple approaches: blanket sudo, specific commands,
        and sudoers file existence."""
        self.has_sudo = False

        # Method 1: blanket sudo -n true
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"], capture_output=True, timeout=3
            )
            if result.returncode == 0:
                self.has_sudo = True
        except Exception:
            pass

        # Method 2: test specific commands likely in sudoers
        if not self.has_sudo:
            for test_cmd in [
                ["sudo", "-n", "purge", "--help"],
                ["sudo", "-n", "/usr/sbin/purge", "--help"],
                ["sudo", "-n", "pmset", "-g"],
            ]:
                try:
                    result = subprocess.run(
                        test_cmd, capture_output=True, timeout=3
                    )
                    if result.returncode == 0:
                        self.has_sudo = True
                        break
                except Exception:
                    pass

        # Method 3: check if sudoers file exists at all
        if not self.has_sudo:
            sudoers_path = Path("/etc/sudoers.d/optimac")
            if sudoers_path.exists():
                self.has_sudo = True

        # Method 4: check if user is in admin group (macOS)
        if not self.has_sudo:
            try:
                result = subprocess.run(
                    ["id", "-Gn"], capture_output=True, text=True, timeout=3
                )
                groups = result.stdout.strip().split()
                if "admin" in groups or "wheel" in groups:
                    # Admin users on macOS can usually sudo with Touch ID
                    self.has_sudo = True
            except Exception:
                pass

        if self.has_sudo:
            self.sudo_label.config(text="SUDO AVAILABLE", fg=self.accent_color)
            self.write_output("Sudo access detected - full features enabled", "accent")
        else:
            self.sudo_label.config(text="NO SUDO - LIMITED FEATURES")
            self.write_output(
                "WARNING: No passwordless sudo - some features limited", "warning"
            )
            self.write_output(
                "Tip: Set up /etc/sudoers.d/optimac for full functionality", "dim"
            )

    def toggle_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.status_label.config(text="MONITORING ACTIVE")
            self.write_output("Starting system monitoring...", "accent")
            threading.Thread(target=self.monitor_system, daemon=True).start()
        else:
            self.monitoring = False
            self.status_label.config(text="MONITORING STOPPED")
            self.write_output("Monitoring stopped", "warning")

    def monitor_system(self):
        while self.monitoring:
            try:
                stats = self.collect_system_stats()
                self.output_queue.put(("monitor_display", stats))
                time.sleep(2)
            except Exception as e:
                self.output_queue.put(("monitor_error", str(e)))
                time.sleep(5)

    def collect_system_stats(self):
        stats = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "cpu_usage": "N/A",
            "memory": {"used": "N/A", "total": "N/A", "percent": "N/A"},
            "power": {"cpu": "N/A", "gpu": "N/A", "npu": "N/A"},
            "network": {"up": "N/A", "down": "N/A"},
            "temperature": "N/A",
        }
        try:
            stats["cpu_usage"] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
        except (AttributeError, OSError):
            pass
        try:
            mem = psutil.virtual_memory()
            compressed = get_compressed_memory_bytes()
            used_with_compressed = mem.used + compressed
            pct = (used_with_compressed / mem.total) * 100 if mem.total else 0
            stats["memory"] = {
                "used": self.network_monitor.format_bytes(used_with_compressed),
                "total": self.network_monitor.format_bytes(mem.total),
                "percent": f"{pct:.1f}%",
            }
        except (AttributeError, OSError):
            pass
        if self.has_sudo:
            power_data = self.silicon_monitor.get_powermetrics_data()
            stats["power"] = {
                "cpu": power_data.get("cpu_power", "N/A"),
                "gpu": power_data.get("gpu_power", "N/A"),
                "npu": power_data.get("ane_power", "N/A"),
            }
        try:
            net_stats = self.network_monitor.get_network_stats()
            stats["network"] = {
                "up": net_stats.get("upload_rate", "N/A"),
                "down": net_stats.get("download_rate", "N/A"),
            }
        except (AttributeError, OSError):
            pass
        if self.has_sudo:
            try:
                result = subprocess.run(
                    ["sudo", "powermetrics", "--samplers", "smc", "-n", "1"],
                    capture_output=True, text=True, timeout=3,
                )
                for line in result.stdout.split("\n"):
                    if "CPU die temperature" in line:
                        stats["temperature"] = line.split(":")[1].strip()
                        break
            except (subprocess.SubprocessError, OSError):
                pass
        return stats

    def display_monitor_stats(self, stats):
        display_text = (
            f"SYSTEM MONITOR [{stats['timestamp']}]\n"
            f"==========================================\n"
            f"CPU Usage:    {stats['cpu_usage']}\n"
            f"Memory:       {stats['memory']['used']} / "
            f"{stats['memory']['total']} ({stats['memory']['percent']})\n"
            f"Temperature:  {stats['temperature']}\n"
            f"POWER CONSUMPTION\n"
            f"CPU Power:    {stats['power']['cpu']}\n"
            f"GPU Power:    {stats['power']['gpu']}\n"
            f"NPU Power:    {stats['power']['npu']}\n"
            f"NETWORK ({self.network_monitor.primary_interface})\n"
            f"Upload:       {stats['network']['up']}\n"
            f"Download:     {stats['network']['down']}\n"
            f"=========================================="
        )
        self.write_output(display_text, "accent")

    # ================================================================
    # Stress tests
    # ================================================================
    def run_cpu_stress(self):
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return
        self.stress_testing = True
        self.status_label.config(text="CPU STRESS TEST")
        self._write_to(
            self.test_terminal,
            f"Starting CPU stress test ({self.stress_duration}s)...", "warning",
        )
        threading.Thread(target=self.cpu_stress_test, daemon=True).start()

    def cpu_stress_test(self):
        try:
            duration = self.stress_duration
            cores_to_use = self.silicon_monitor.chip_info["cpu_cores"]
            self.output_queue.put(("stress_update", f"Utilizing {cores_to_use} CPU cores"))
            stop_event = multiprocessing.Event()
            processes = []
            for i in range(cores_to_use):
                p = multiprocessing.Process(
                    target=self.stress_engine.cpu_stress_worker,
                    args=(i, duration, stop_event),
                )
                p.start()
                processes.append(p)
            for i in range(duration):
                if not self.stress_testing:
                    stop_event.set()
                    break
                self.output_queue.put(
                    ("stress_update", f"CPU test progress: {i+1}/{duration} seconds")
                )
                time.sleep(1)
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
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return
        self.stress_testing = True
        self.status_label.config(text="MEMORY STRESS TEST")
        self._write_to(self.test_terminal, "Starting memory stress test...", "warning")
        threading.Thread(target=self.memory_stress_test, daemon=True).start()

    def memory_stress_test(self):
        try:
            available_mb = psutil.virtual_memory().available // (1024 * 1024)
            target_mb = min(available_mb // 2, 1000)
            self.output_queue.put(("stress_update", f"Allocating {target_mb}MB of memory"))
            result = self.stress_engine.memory_stress_worker(target_mb)
            self.output_queue.put(
                ("stress_complete", f"Memory test completed - allocated {result}MB")
            )
        except Exception as e:
            self.output_queue.put(("stress_error", f"Memory stress test error: {e}"))
        finally:
            self.stress_testing = False

    def run_combined_stress(self):
        if self.stress_testing:
            self._write_to(self.test_terminal, "Stress test already running", "warning")
            return
        self.stress_testing = True
        self.status_label.config(text="COMBINED STRESS TEST")
        self._write_to(
            self.test_terminal,
            f"Starting combined stress ({self.stress_duration}s)...", "warning",
        )

        def combined():
            try:
                dur = self.stress_duration
                cores = self.silicon_monitor.chip_info["cpu_cores"]
                self.output_queue.put(
                    ("stress_update", f"CPU: {cores} cores + Memory allocation")
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
                self.output_queue.put(("stress_update", f"Allocating {target}MB memory"))
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
                self.output_queue.put(("stress_complete", "Combined stress test completed"))
            except Exception as e:
                self.output_queue.put(("stress_error", f"Combined test error: {e}"))
            finally:
                self.stress_testing = False

        threading.Thread(target=combined, daemon=True).start()

    # ================================================================
    # Optimization actions
    # ================================================================
    def run_optimization(self):
        self.status_label.config(text="OPTIMIZING SYSTEM")
        self.write_output("Starting system optimization...", "accent")
        threading.Thread(target=self.optimization_thread, daemon=True).start()

    def optimization_thread(self):
        if self.has_sudo:
            commands = [
                ("Clearing DNS cache", "dscacheutil -flushcache && killall -HUP mDNSResponder"),
                ("Purging inactive memory", "purge"),
                ("Enabling high performance mode", "pmset -a highpowermode 1"),
                ("Disabling sleep", "pmset -a sleep 0"),
                ("Clearing system caches", "rm -rf /System/Library/Caches/* 2>/dev/null || true"),
                ("Rebuilding font cache",
                 "atsutil databases -removeUser && atsutil server -shutdown && atsutil server -ping"),
            ]
        else:
            commands = [
                ("Clearing user DNS cache", "dscacheutil -flushcache"),
                ("Clearing user caches", "rm -rf ~/Library/Caches/com.apple.* 2>/dev/null || true"),
                ("Clearing user font cache", "atsutil databases -removeUser"),
                ("Restarting Dock", "killall Dock"),
                ("Clearing user logs", "rm -rf ~/Library/Logs/* 2>/dev/null || true"),
                ("Restarting user services", "launchctl kickstart -k gui/$(id -u)/com.apple.Dock"),
            ]
        for description, cmd in commands:
            self.output_queue.put(("optimize_step", (description, cmd)))
            time.sleep(1)
        self.output_queue.put(("optimize_complete", "System optimization completed"))

    def _run_opt_cmd(self, cmd, description):
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
        threading.Thread(target=run, daemon=True).start()

    def _purge_memory(self):
        self._run_opt_cmd("purge", "Purging inactive memory")

    def _flush_dns(self):
        self._run_opt_cmd(
            "dscacheutil -flushcache && sudo killall -HUP mDNSResponder",
            "Flushing DNS cache",
        )

    def _flush_routes(self):
        self._run_opt_cmd("sudo route -n flush", "Flushing network routes")

    def _clear_caches(self):
        self._run_opt_cmd(
            "rm -rf ~/Library/Caches/com.apple.* 2>/dev/null || true",
            "Clearing user caches",
        )

    def _apply_power_profile(self):
        profile = self.power_var.get()
        if profile == "ai_server":
            cmds = (
                "sudo pmset -a sleep 0 && "
                "sudo pmset -a disksleep 0 && "
                "sudo pmset -a highpowermode 1"
            )
            desc = "Applying AI Server power profile"
        elif profile == "low_power":
            cmds = "sudo pmset -a lowpowermode 1 && sudo pmset -a sleep 10"
            desc = "Applying Low Power profile"
        else:
            cmds = "sudo pmset restoredefaults"
            desc = "Restoring default power profile"
        self._run_opt_cmd(cmds, desc)

    # ================================================================
    # AI Stack actions
    # ================================================================
    def _ai_start(self, service):
        def run():
            msg = self.ai_manager.start_service(service)
            self._write_to(self.ai_terminal, msg, "accent")
            time.sleep(2)
            self._refresh_ai_status()
        threading.Thread(target=run, daemon=True).start()

    def _ai_stop(self, service):
        def run():
            msg = self.ai_manager.stop_service(service)
            self._write_to(self.ai_terminal, msg, "warning")
            time.sleep(1)
            self._refresh_ai_status()
        threading.Thread(target=run, daemon=True).start()

    def _refresh_ai_status(self):
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
                    "running": "RUNNING",
                    "stopped": "STOPPED",
                    "not_installed": "NOT INSTALLED",
                }
                lbl.config(
                    text=icon_map.get(status, status),
                    fg=color_map.get(status, self.fg_color),
                )
        threading.Thread(target=run, daemon=True).start()

    def _list_models(self):
        def run():
            self._write_to(self.ai_terminal, "Fetching Ollama models...", "command")
            out = self.ai_manager.list_ollama_models()
            for line in out.split("\n"):
                self._write_to(self.ai_terminal, f"  {line}", "accent")
        threading.Thread(target=run, daemon=True).start()

    def _pull_model(self):
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
                    self.ai_terminal, f"Model {name} pulled successfully!", "accent"
                )
            else:
                self._write_to(self.ai_terminal, f"Failed to pull {name}", "error")
        threading.Thread(target=run, daemon=True).start()

    def _browse_models(self):
        """Browse filesystem for downloaded models."""
        from tkinter import filedialog
        base = self._current_config.get("modelBaseDir", "")
        search_dirs = [base] if base and os.path.isdir(base) else []
        # Add common model directories
        home = os.path.expanduser("~")
        for d in [
            os.path.join(home, ".ollama", "models"),
            os.path.join(home, ".cache", "huggingface", "hub"),
            os.path.join(home, ".cache", "lm-studio", "models"),
            os.path.join(home, "models"),
            "/Volumes/M2 Raid0/models",
        ]:
            if os.path.isdir(d) and d not in search_dirs:
                search_dirs.append(d)

        def run():
            self._write_to(self.ai_terminal, "Scanning for downloaded models...", "command")
            found = []
            for search_dir in search_dirs:
                self._write_to(self.ai_terminal, f"  Scanning: {search_dir}", "dim")
                try:
                    for root_dir, dirs, files in os.walk(search_dir):
                        depth = root_dir.replace(search_dir, "").count(os.sep)
                        if depth > 3:
                            dirs.clear()
                            continue
                        for f in files:
                            if f.endswith((".gguf", ".bin", ".safetensors", ".pth", ".pt", ".onnx")):
                                full = os.path.join(root_dir, f)
                                size_mb = os.path.getsize(full) / (1024 * 1024)
                                if size_mb > 50:
                                    found.append((full, size_mb))
                except PermissionError:
                    pass
            if found:
                found.sort(key=lambda x: -x[1])
                self._write_to(
                    self.ai_terminal,
                    f"Found {len(found)} model files:", "accent",
                )
                for path, size in found[:30]:
                    if size > 1024:
                        size_str = f"{size/1024:.1f}GB"
                    else:
                        size_str = f"{size:.0f}MB"
                    short = path.replace(home, "~")
                    self._write_to(self.ai_terminal, f"  [{size_str:>8}] {short}", "success")
            else:
                self._write_to(
                    self.ai_terminal,
                    "No model files found. Set a model base directory in the Model Directory section.",
                    "warning",
                )
        threading.Thread(target=run, daemon=True).start()

    def _browse_model_dir(self):
        """Open folder picker for model base directory."""
        from tkinter import filedialog
        current = self.model_dir_var.get()
        initial = current if current and os.path.isdir(current) else os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            title="Select Model Base Directory",
            initialdir=initial,
        )
        if chosen:
            self.model_dir_var.set(chosen)

    def _save_model_dir(self):
        """Save model base directory to config."""
        path = self.model_dir_var.get().strip()
        if path and not os.path.isdir(path):
            self._write_to(self.ai_terminal, f"Directory does not exist: {path}", "error")
            return
        self._current_config["modelBaseDir"] = path
        self.config_manager.save(self._current_config)
        if path:
            self._write_to(self.ai_terminal, f"Model base directory set: {path}", "accent")
        else:
            self._write_to(self.ai_terminal, "Model base directory cleared", "warning")

    def _pick_model_file(self):
        """Open file picker for a model file to serve."""
        from tkinter import filedialog
        base = self.model_dir_var.get() if hasattr(self, "model_dir_var") else ""
        initial = base if base and os.path.isdir(base) else os.path.expanduser("~")
        chosen = filedialog.askopenfilename(
            title="Select Model File",
            initialdir=initial,
            filetypes=[
                ("GGUF Models", "*.gguf"),
                ("SafeTensors", "*.safetensors"),
                ("PyTorch", "*.bin *.pth *.pt"),
                ("ONNX", "*.onnx"),
                ("All Files", "*.*"),
            ],
        )
        if chosen:
            self.serve_model_var.set(chosen)

    def _serve_model(self):
        """Start serving a model with the selected runtime."""
        model = self.serve_model_var.get().strip()
        if not model:
            self._write_to(self.ai_terminal, "Enter a model name or path first", "warning")
            return
        runtime = self.serve_runtime_var.get()

        def run():
            if runtime == "ollama":
                self._write_to(
                    self.ai_terminal,
                    f"Loading model into Ollama: {model}", "command",
                )
                self._write_to(
                    self.ai_terminal,
                    "Starting Ollama server if needed...", "dim",
                )
                proc = self.ai_manager.serve_model_ollama(model)
                if proc is None:
                    self._write_to(
                        self.ai_terminal,
                        "Ollama not installed. Install from https://ollama.com", "error",
                    )
                    return
                # Read output
                try:
                    for line in proc.stdout:
                        line = line.strip()
                        if line:
                            self._write_to(self.ai_terminal, f"  {line}", "accent")
                    proc.wait(timeout=30)
                except Exception:
                    pass
                self._write_to(
                    self.ai_terminal,
                    f"Model '{model}' loaded in Ollama (API at :11434)", "accent",
                )
                time.sleep(1)
                self._refresh_ai_status()

            elif runtime == "mlx":
                port = self.ai_manager.SERVICES["mlx"]["port"]
                self._write_to(
                    self.ai_terminal,
                    f"Starting MLX server with: {model} on port {port}", "command",
                )
                # Stop any existing MLX server first
                self.ai_manager.stop_service("mlx")
                time.sleep(1)
                proc = self.ai_manager.serve_model_mlx(model, port)
                if proc is None:
                    self._write_to(
                        self.ai_terminal,
                        "MLX not available. Install: pip install mlx-lm", "error",
                    )
                    return
                # Read first few lines of output
                try:
                    for i in range(10):
                        line = proc.stdout.readline()
                        if not line:
                            break
                        line = line.strip()
                        if line:
                            self._write_to(self.ai_terminal, f"  {line}", "accent")
                        if "running" in line.lower() or "listening" in line.lower():
                            break
                except Exception:
                    pass
                self._write_to(
                    self.ai_terminal,
                    f"MLX server started on port {port}", "accent",
                )
                time.sleep(1)
                self._refresh_ai_status()

        threading.Thread(target=run, daemon=True).start()

    def _show_running_models(self):
        """Show currently running/loaded models."""
        def run():
            self._write_to(self.ai_terminal, "Checking running models...", "command")
            # Ollama running models
            out = self.ai_manager.get_ollama_running_models()
            self._write_to(self.ai_terminal, "OLLAMA RUNNING MODELS:", "accent")
            for line in out.split("\n"):
                if line.strip():
                    self._write_to(self.ai_terminal, f"  {line}", "success")
            # Check MLX
            port = self.ai_manager.SERVICES["mlx"]["port"]
            if self.ai_manager.check_port(port):
                self._write_to(
                    self.ai_terminal,
                    f"MLX server is running on port {port}", "accent",
                )
            else:
                self._write_to(self.ai_terminal, "MLX server: not running", "dim")
        threading.Thread(target=run, daemon=True).start()

    # ================================================================
    # Maintenance actions
    # ================================================================
    def _run_maintenance(self):
        steps = [
            ("Check memory pressure", "memory_pressure"),
            ("Flush DNS cache", "dscacheutil -flushcache"),
            ("Clear user caches", "rm -rf ~/Library/Caches/com.apple.* 2>/dev/null || true"),
            ("Clear user logs", "rm -rf ~/Library/Logs/* 2>/dev/null || true"),
            ("Rebuild Spotlight index", "mdutil -E / 2>/dev/null || true"),
            ("Flush routes", "sudo route -n flush 2>/dev/null || true"),
            ("Purge memory", "purge 2>/dev/null || true"),
            ("Restart Dock", "killall Dock"),
        ]

        def run():
            self._write_to(self.maint_terminal, "=== MAINTENANCE CYCLE STARTED ===", "accent")
            for i, (desc, cmd) in enumerate(steps, 1):
                self._write_to(self.maint_terminal, f"[{i}/{len(steps)}] {desc}...", "command")
                try:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
                    self._write_to(self.maint_terminal, f"    OK: {desc} complete", "accent")
                except Exception as e:
                    self._write_to(self.maint_terminal, f"    FAIL: {desc} ({e})", "error")
                time.sleep(0.5)
            self._write_to(self.maint_terminal, "=== MAINTENANCE CYCLE COMPLETE ===", "accent")
            self.status_label.config(text="READY")

        self.status_label.config(text="MAINTENANCE RUNNING")
        threading.Thread(target=run, daemon=True).start()

    def _check_memory_pressure(self):
        def run():
            try:
                mem = psutil.virtual_memory()
                pct = mem.percent
                avail_gb = mem.available / (1024 ** 3)
                total_gb = mem.total / (1024 ** 3)
                bar_len = 30
                filled = int(bar_len * pct / 100)
                bar = "#" * filled + "-" * (bar_len - filled)
                warn = self._current_config.get("memoryWarningThreshold", 0.75) * 100
                crit = self._current_config.get("memoryCriticalThreshold", 0.90) * 100
                if pct > crit:
                    level, tag = "CRITICAL", "error"
                elif pct > warn:
                    level, tag = "WARNING", "warning"
                else:
                    level, tag = "NOMINAL", "accent"
                self._write_to(self.maint_terminal, f"Memory Pressure: {level}", tag)
                self._write_to(self.maint_terminal, f"  [{bar}] {pct:.1f}%", tag)
                self._write_to(
                    self.maint_terminal,
                    f"  Available: {avail_gb:.1f}GB / {total_gb:.1f}GB", tag,
                )
                self._write_to(
                    self.maint_terminal,
                    f"  Thresholds: warn={warn:.0f}% crit={crit:.0f}%", "dim",
                )
            except Exception as e:
                self._write_to(self.maint_terminal, f"Error checking memory: {e}", "error")
        threading.Thread(target=run, daemon=True).start()

    def _view_config(self):
        config = self.config_manager.load()
        self._write_to(self.maint_terminal, "=== CURRENT CONFIGURATION ===", "accent")
        for line in json.dumps(config, indent=2).split("\n"):
            self._write_to(self.maint_terminal, f"  {line}", "command")

    def _load_protected_list(self):
        config = self.config_manager.load()
        procs = config.get("protectedProcesses", [])
        self.prot_listbox.delete(0, tk.END)
        for p in procs:
            self.prot_listbox.insert(tk.END, p)

    def _add_protected(self):
        name = self.prot_entry.get().strip()
        if not name:
            return
        self.config_manager.add_protected(name)
        self.prot_entry.delete(0, tk.END)
        self._load_protected_list()
        self._current_config = self.config_manager.load()
        self._write_to(self.maint_terminal, f"Added '{name}' to protected list", "accent")

    def _remove_protected(self):
        sel = self.prot_listbox.curselection()
        if not sel:
            return
        name = self.prot_listbox.get(sel[0])
        self.config_manager.remove_protected(name)
        self._load_protected_list()
        self._current_config = self.config_manager.load()
        self._write_to(self.maint_terminal, f"Removed '{name}' from protected list", "warning")

    def clear_terminal(self):
        self.terminal_output.config(state="normal")
        self.terminal_output.delete(1.0, "end")
        self.terminal_output.config(state="disabled")
        self.write_output("Terminal cleared", "accent")

    def quit_app(self):
        if self._config_dirty:
            if messagebox.askyesno("Unsaved Settings", "Save settings before quitting?"):
                self._save_settings()
        self.monitoring = False
        self.stress_testing = False
        self.write_output("Shutting down GerdsenAI OptiMac...", "warning")
        self.root.after(500, self.root.quit)

    def start_queue_processor(self):
        self.process_queue()

    def process_queue(self):
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
    if platform.system() != "Darwin":
        print("ERROR: This tool is designed for macOS only.")
        sys.exit(1)
    try:
        import psutil  # noqa: F401
    except ImportError:
        print("ERROR: psutil module required. Install with: pip install psutil")
        sys.exit(1)
    root = tk.Tk()
    GerdsenAIOptiMac(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)


if __name__ == "__main__":
    main()
