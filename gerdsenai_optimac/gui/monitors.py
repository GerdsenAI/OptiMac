"""
System monitoring classes for Apple Silicon Macs.
Extracted from gerdsenai_optimac_improved.py v2.3.
"""

import os
import re
import time
import subprocess
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
    """Detect and monitor Apple Silicon chip capabilities."""

    def __init__(self):
        self.chip_info = self.detect_chip()

    def detect_chip(self):
        """Detect Apple Silicon chip model and capabilities."""
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
                capture_output=True, text=True, timeout=5,
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
                    ).decode().strip()
                )
                eff_cores = int(
                    subprocess.check_output(
                        ["sysctl", "-n", "hw.perflevel1.physicalcpu"]
                    ).decode().strip()
                )
                info["cpu_cores"] = perf_cores + eff_cores
                info["perf_cores"] = perf_cores
                info["eff_cores"] = eff_cores
                gpu_result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5,
                )
                gpu_cores_detected = False
                if "Total Number of Cores" in gpu_result.stdout:
                    match = re.search(r"Total Number of Cores:\s*(\d+)", gpu_result.stdout)
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True
                if not gpu_cores_detected and "GPU Cores" in gpu_result.stdout:
                    match = re.search(r"GPU Cores:\s*(\d+)", gpu_result.stdout)
                    if match:
                        info["gpu_cores"] = int(match.group(1))
                        gpu_cores_detected = True
                if not gpu_cores_detected and "Metal" in gpu_result.stdout:
                    metal_match = re.search(r"(\d+)\s*(?:GPU\s*)?[Cc]ores?", gpu_result.stdout)
                    if metal_match:
                        info["gpu_cores"] = int(metal_match.group(1))
            except (subprocess.SubprocessError, ValueError, OSError):
                info["cpu_cores"] = os.cpu_count() or 8
        except Exception as e:
            print(f"Chip detection error: {e}")
        return info

    def get_chip_capabilities(self, model):
        """Get known capabilities for specific chip models."""
        capabilities = {
            "M1": {"gpu_cores": 7, "memory_bandwidth": 68.25, "neural_tops": 11},
            "M1 Pro": {"gpu_cores": 14, "memory_bandwidth": 200, "neural_tops": 11},
            "M1 Max": {"gpu_cores": 24, "memory_bandwidth": 400, "neural_tops": 11},
            "M1 Ultra": {"gpu_cores": 48, "memory_bandwidth": 800, "neural_tops": 22},
            "M2": {"gpu_cores": 8, "memory_bandwidth": 100, "neural_tops": 15.8},
            "M2 Pro": {"gpu_cores": 16, "memory_bandwidth": 200, "neural_tops": 15.8},
            "M2 Max": {"gpu_cores": 30, "memory_bandwidth": 400, "neural_tops": 15.8},
            "M2 Ultra": {"gpu_cores": 60, "memory_bandwidth": 800, "neural_tops": 31.6},
            "M3": {"gpu_cores": 8, "memory_bandwidth": 100, "neural_tops": 18},
            "M3 Pro": {"gpu_cores": 14, "memory_bandwidth": 150, "neural_tops": 18},
            "M3 Max": {"gpu_cores": 30, "memory_bandwidth": 400, "neural_tops": 18},
            "M4": {"gpu_cores": 8, "memory_bandwidth": 120, "neural_tops": 38},
            "M4 Pro": {"gpu_cores": 16, "memory_bandwidth": 273, "neural_tops": 38},
            "M4 Max": {"gpu_cores": 32, "memory_bandwidth": 546, "neural_tops": 38},
        }
        try:
            not_known = model not in capabilities or "gpu_cores" not in capabilities[model]
            if not_known:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5,
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
        """Get power consumption data for CPU, GPU, and ANE."""
        if os.geteuid() != 0:
            return {"cpu_power": "N/A", "gpu_power": "N/A", "ane_power": "N/A"}
        cmd = [
            "powermetrics", "-i", str(duration * 1000), "-n", "1",
            "--samplers", "cpu_power,gpu_power,ane_power",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return self.parse_powermetrics(result.stdout)
        except Exception:
            return {"cpu_power": "N/A", "gpu_power": "N/A", "ane_power": "N/A"}

    def parse_powermetrics(self, output):
        """Parse powermetrics output for power values."""
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
    """Monitor network interface statistics."""

    def __init__(self):
        self.last_stats = None
        self.last_time = None
        self.primary_interface = self.get_primary_interface()

    def get_primary_interface(self):
        """Detect primary network interface on macOS."""
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
        """Get current network statistics with rate calculation."""
        try:
            current_time = time.time()
            stats = psutil.net_io_counters(pernic=True)
            primary_stats = stats.get(self.primary_interface)
            if not primary_stats:
                return {
                    "interface": self.primary_interface,
                    "bytes_sent": "N/A", "bytes_recv": "N/A",
                    "upload_rate": "N/A", "download_rate": "N/A",
                }
            upload_rate = download_rate = "N/A"
            if self.last_stats and self.last_time:
                time_delta = current_time - self.last_time
                if time_delta > 0:
                    upload_rate = (primary_stats.bytes_sent - self.last_stats.bytes_sent) / time_delta
                    download_rate = (primary_stats.bytes_recv - self.last_stats.bytes_recv) / time_delta
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
                "bytes_sent": "N/A", "bytes_recv": "N/A",
                "upload_rate": "N/A", "download_rate": "N/A",
            }

    def format_bytes(self, bytes_val):
        """Format bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}PB"
