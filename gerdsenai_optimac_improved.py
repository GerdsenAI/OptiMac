#!/usr/bin/env python3
"""
GerdsenAI OptiMac - Improved Mac Performance Optimizer
Enhanced performance monitoring and optimization for Apple Silicon Macs
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
import psutil

class AppleSiliconMonitor:
    def __init__(self):
        self.chip_info = self.detect_chip()
        
    def detect_chip(self):
        """Detect Apple Silicon chip model and capabilities"""
        info = {
            'model': 'Unknown',
            'generation': 0,
            'cpu_cores': 0,
            'gpu_cores': 0,
            'neural_cores': 16,
            'memory_bandwidth': 0,
            'perf_cores': 0,
            'eff_cores': 0
        }
        
        try:
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                                  capture_output=True, text=True, timeout=5)
            
            if 'Apple M' in result.stdout:
                match = re.search(r'Apple M(\d+)( Pro| Max| Ultra)?', result.stdout)
                if match:
                    generation = int(match.group(1))
                    variant = match.group(2) or ''
                    
                    info['model'] = f"M{generation}{variant.strip()}"
                    info['generation'] = generation
                    info.update(self.get_chip_capabilities(info['model']))
            
            # Get actual core counts and try to get GPU cores more accurately
            try:
                perf_cores = int(subprocess.check_output(
                    ['sysctl', '-n', 'hw.perflevel0.physicalcpu']
                ).decode().strip())
                eff_cores = int(subprocess.check_output(
                    ['sysctl', '-n', 'hw.perflevel1.physicalcpu']
                ).decode().strip())
                info['cpu_cores'] = perf_cores + eff_cores
                info['perf_cores'] = perf_cores
                info['eff_cores'] = eff_cores
                
                # Try to get more accurate GPU core count using multiple methods
                gpu_result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                          capture_output=True, text=True, timeout=5)
                gpu_cores_detected = False
                
                # Method 1: Look for "Total Number of Cores"
                if 'Total Number of Cores' in gpu_result.stdout:
                    match = re.search(r'Total Number of Cores:\s*(\d+)', gpu_result.stdout)
                    if match:
                        info['gpu_cores'] = int(match.group(1))
                        gpu_cores_detected = True
                
                # Method 2: Look for GPU cores in different format
                if not gpu_cores_detected and 'GPU Cores' in gpu_result.stdout:
                    match = re.search(r'GPU Cores:\s*(\d+)', gpu_result.stdout)
                    if match:
                        info['gpu_cores'] = int(match.group(1))
                        gpu_cores_detected = True
                
                # Method 3: Try to parse Metal info
                if not gpu_cores_detected and 'Metal' in gpu_result.stdout:
                    # Look for core count in Metal capabilities
                    metal_match = re.search(r'(\d+)\s*(?:GPU\s*)?[Cc]ores?', gpu_result.stdout)
                    if metal_match:
                        info['gpu_cores'] = int(metal_match.group(1))
                        gpu_cores_detected = True
                        
            except:
                info['cpu_cores'] = os.cpu_count() or 8
                
        except Exception as e:
            print(f"Chip detection error: {e}")
        
        return info
    
    def get_chip_capabilities(self, model):
        """Get known capabilities for specific chip models"""
        capabilities = {
            'M1': {'gpu_cores': 7, 'memory_bandwidth': 68.25, 'neural_tops': 11},
            'M1 Pro': {'gpu_cores': 14, 'memory_bandwidth': 200, 'neural_tops': 11},
            'M1 Max': {'gpu_cores': 24, 'memory_bandwidth': 400, 'neural_tops': 11},
            'M1 Ultra': {'gpu_cores': 48, 'memory_bandwidth': 800, 'neural_tops': 22},
            'M2': {'gpu_cores': 8, 'memory_bandwidth': 100, 'neural_tops': 15.8},
            'M2 Pro': {'gpu_cores': 16, 'memory_bandwidth': 200, 'neural_tops': 15.8},
            'M2 Max': {'gpu_cores': 30, 'memory_bandwidth': 400, 'neural_tops': 15.8},
            'M2 Ultra': {'gpu_cores': 60, 'memory_bandwidth': 800, 'neural_tops': 31.6},
            'M3': {'gpu_cores': 8, 'memory_bandwidth': 100, 'neural_tops': 18},
            'M3 Pro': {'gpu_cores': 14, 'memory_bandwidth': 150, 'neural_tops': 18},
            'M3 Max': {'gpu_cores': 30, 'memory_bandwidth': 400, 'neural_tops': 18},
            'M4': {'gpu_cores': 8, 'memory_bandwidth': 120, 'neural_tops': 38},
            'M4 Pro': {'gpu_cores': 16, 'memory_bandwidth': 273, 'neural_tops': 38},
            'M4 Max': {'gpu_cores': 32, 'memory_bandwidth': 546, 'neural_tops': 38}
        }
        
        # Try to detect actual GPU cores from system_profiler if not already detected
        try:
            if model not in capabilities or 'gpu_cores' not in capabilities[model]:
                result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                      capture_output=True, text=True, timeout=5)
                if 'Total Number of Cores' in result.stdout:
                    match = re.search(r'Total Number of Cores:\s*(\d+)', result.stdout)
                    if match:
                        actual_cores = int(match.group(1))
                        if model in capabilities:
                            capabilities[model]['gpu_cores'] = actual_cores
                        else:
                            capabilities[model] = {'gpu_cores': actual_cores, 'memory_bandwidth': 100, 'neural_tops': 15}
        except:
            pass
            
        return capabilities.get(model, {'gpu_cores': 8, 'memory_bandwidth': 100, 'neural_tops': 15})
    
    def get_powermetrics_data(self, duration=1):
        """Get power consumption data for CPU, GPU, and ANE"""
        if os.geteuid() != 0:
            return {'cpu_power': 'N/A', 'gpu_power': 'N/A', 'ane_power': 'N/A'}
            
        cmd = [
            'powermetrics', 
            '-i', str(duration * 1000),
            '-n', '1',
            '--samplers', 'cpu_power,gpu_power,ane_power'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return self.parse_powermetrics(result.stdout)
        except Exception:
            return {'cpu_power': 'N/A', 'gpu_power': 'N/A', 'ane_power': 'N/A'}
    
    def parse_powermetrics(self, output):
        """Parse powermetrics output for power values"""
        data = {'cpu_power': 'N/A', 'gpu_power': 'N/A', 'ane_power': 'N/A'}
        
        patterns = {
            'cpu_power': r'CPU Power:\s*(\d+\.?\d*)\s*mW',
            'gpu_power': r'GPU Power:\s*(\d+\.?\d*)\s*mW',
            'ane_power': r'ANE Power:\s*(\d+\.?\d*)\s*mW'
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
            result = subprocess.run(['route', 'get', 'default'], 
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'interface:' in line:
                    return line.split(':')[1].strip()
        except:
            pass
        
        # Fallback: return first active non-loopback interface
        interfaces = psutil.net_if_stats()
        for name, stats in interfaces.items():
            if stats.isup and not name.startswith('lo'):
                return name
        
        return 'en0'
    
    def get_network_stats(self):
        """Get current network statistics"""
        try:
            current_time = time.time()
            
            # Get stats for all interfaces
            stats = psutil.net_io_counters(pernic=True)
            primary_stats = stats.get(self.primary_interface)
            
            if not primary_stats:
                return {
                    'interface': self.primary_interface,
                    'bytes_sent': 'N/A',
                    'bytes_recv': 'N/A',
                    'upload_rate': 'N/A',
                    'download_rate': 'N/A'
                }
            
            # Calculate rates if we have previous data
            upload_rate = download_rate = 'N/A'
            if self.last_stats and self.last_time:
                time_delta = current_time - self.last_time
                if time_delta > 0:
                    upload_rate = (primary_stats.bytes_sent - self.last_stats.bytes_sent) / time_delta
                    download_rate = (primary_stats.bytes_recv - self.last_stats.bytes_recv) / time_delta
                    upload_rate = self.format_bytes(upload_rate) + '/s'
                    download_rate = self.format_bytes(download_rate) + '/s'
            
            # Store current stats for next calculation
            self.last_stats = primary_stats
            self.last_time = current_time
            
            return {
                'interface': self.primary_interface,
                'bytes_sent': self.format_bytes(primary_stats.bytes_sent),
                'bytes_recv': self.format_bytes(primary_stats.bytes_recv),
                'upload_rate': upload_rate,
                'download_rate': download_rate
            }
            
        except Exception as e:
            return {
                'interface': 'Error',
                'bytes_sent': 'N/A',
                'bytes_recv': 'N/A',
                'upload_rate': 'N/A',
                'download_rate': 'N/A'
            }
    
    def format_bytes(self, bytes_val):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
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
        
        while not stop_event.is_set() and (time.time() - start_time) < duration:
            # Prime number calculation
            n = 982451653
            is_prime = all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1))
            
            # Floating point operations
            result = sum(math.sin(i) * math.cos(i) * math.sqrt(i + 1) 
                        for i in range(1000))
            
            # Matrix operations (lightweight without numpy dependency)
            if operations % 10 == 0:
                a = [[random.random() for _ in range(50)] for _ in range(50)]
                b = [[random.random() for _ in range(50)] for _ in range(50)]
                # Partial matrix multiplication
                c = [[sum(a[i][k] * b[k][j] for k in range(50)) 
                     for j in range(25)] for i in range(25)]
            
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
                    block[j:j+8] = (i * j).to_bytes(8, 'little')
                allocated_blocks.append(block)
                
                # Prevent unlimited growth
                if len(allocated_blocks) > 100:
                    allocated_blocks.pop(0)
                    
        except MemoryError:
            pass
        
        return len(allocated_blocks)

class CommandExecutor:
    def __init__(self, terminal_widget):
        self.terminal = terminal_widget
        
    def execute_command(self, command, description=None):
        """Execute system command and display in terminal"""
        if description:
            self.terminal.write_output(f"{description}...", 'warning')
        
        self.terminal.write_output(f"$ {command}", 'command')
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                # Filter out excessive output
                output_lines = result.stdout.strip().split('\n')
                if len(output_lines) > 10:
                    self.terminal.write_output(f"Output: {len(output_lines)} lines processed", 'success')
                else:
                    self.terminal.write_output(result.stdout.strip(), 'success')
            
            if result.stderr:
                # Filter common harmless errors
                stderr_clean = result.stderr.strip()
                if not any(harmless in stderr_clean.lower() for harmless in 
                          ['no such file', 'operation not permitted', 'permission denied']):
                    self.terminal.write_output(stderr_clean, 'error')
                elif 'permission denied' in stderr_clean.lower():
                    self.terminal.write_output("Permission denied - try running with sudo", 'warning')
                else:
                    self.terminal.write_output("Command completed with warnings", 'warning')
            
            if result.returncode == 0:
                self.terminal.write_output("Command completed successfully", 'success')
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            self.terminal.write_output("Command timed out", 'error')
            return False
        except Exception as e:
            self.terminal.write_output(f"Error: {str(e)}", 'error')
            return False

class GerdsenAIOptiMac:
    def __init__(self, root):
        self.root = root
        self.root.title("GerdsenAI OptiMac v2.0 - Terminal Edition")
        self.root.geometry("1000x750")
        self.root.configure(bg='#000000')
        
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
        
        # State variables
        self.monitoring = False
        self.stress_testing = False
        self.output_queue = queue.Queue()
        
        # Create GUI
        self.create_interface()
        self.start_queue_processor()
        
        # Check sudo status
        self.check_sudo_status()
        
    def create_interface(self):
        """Create retro terminal interface"""
        # ASCII Banner
        self.create_banner()
        
        # System info
        self.create_system_info()
        
        # Terminal output area
        self.create_terminal()
        
        # Control buttons
        self.create_controls()
        
        # Status bar
        self.create_status_bar()
        
    def create_banner(self):
        """Create ASCII art banner"""
        banner_frame = tk.Frame(self.root, bg=self.bg_color)
        banner_frame.pack(fill='x', padx=10, pady=5)
        
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
            font=('Courier New', 7, 'bold'),
            justify='left'
        )
        banner_label.pack()
        
    def create_system_info(self):
        """Create system information display"""
        info_frame = tk.Frame(self.root, bg=self.bg_color)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        chip = self.silicon_monitor.chip_info
        info_text = (f"SYSTEM: Apple {chip['model']} | "
                    f"CPU: {chip.get('perf_cores', 'N/A')}P+{chip.get('eff_cores', 'N/A')}E cores | "
                    f"GPU: {chip.get('gpu_cores', 'N/A')} cores | "
                    f"NPU: {chip['neural_cores']} cores ({chip.get('neural_tops', 'N/A')} TOPS)")
        
        info_label = tk.Label(
            info_frame,
            text=info_text,
            bg=self.bg_color,
            fg=self.accent_color,
            font=('Courier New', 10, 'bold')
        )
        info_label.pack()
        
    def create_terminal(self):
        """Create terminal output area"""
        terminal_frame = tk.Frame(self.root, bg=self.bg_color)
        terminal_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Terminal with scrollbar
        self.terminal_output = scrolledtext.ScrolledText(
            terminal_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            insertbackground=self.fg_color,
            font=('Courier New', 10),
            wrap=tk.WORD,
            height=25,
            state='disabled',
            cursor='arrow'
        )
        self.terminal_output.pack(fill='both', expand=True)
        
        # Configure text tags for colors
        self.terminal_output.tag_config('command', foreground=self.command_color)
        self.terminal_output.tag_config('error', foreground=self.error_color)
        self.terminal_output.tag_config('warning', foreground=self.warning_color)
        self.terminal_output.tag_config('success', foreground=self.fg_color)
        self.terminal_output.tag_config('accent', foreground=self.accent_color)
        
        # Initialize command executor
        self.command_executor = CommandExecutor(self)
        
        # Welcome message
        self.write_output("GerdsenAI OptiMac Terminal v2.0 Initialized", 'accent')
        self.write_output("Ready for performance optimization and monitoring", 'success')
        
    def create_controls(self):
        """Create control buttons"""
        control_frame = tk.Frame(self.root, bg=self.bg_color)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Button style
        button_config = {
            'bg': '#002200',
            'fg': self.fg_color,
            'font': ('Courier New', 10, 'bold'),
            'relief': 'raised',
            'bd': 2,
            'padx': 15,
            'pady': 8,
            'activebackground': '#004400',
            'activeforeground': self.accent_color
        }
        
        buttons = [
            ("MONITOR", self.toggle_monitoring),
            ("CPU TEST", self.run_cpu_stress),
            ("MEM TEST", self.run_memory_stress),
            ("OPTIMIZE", self.run_optimization),
            ("CLEAR", self.clear_terminal),
            ("EXIT", self.quit_app)
        ]
        
        for text, command in buttons:
            btn = tk.Button(control_frame, text=text, command=command, **button_config)
            btn.pack(side='left', padx=5)
            
            # Hover effects
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#004400'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#002200'))
        
    def create_status_bar(self):
        """Create status bar"""
        status_frame = tk.Frame(self.root, bg='#001100', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="READY",
            bg='#001100',
            fg=self.fg_color,
            font=('Courier New', 10, 'bold')
        )
        self.status_label.pack(side='left', padx=10, pady=5)
        
        self.sudo_label = tk.Label(
            status_frame,
            text="",
            bg='#001100',
            fg=self.warning_color,
            font=('Courier New', 10)
        )
        self.sudo_label.pack(side='right', padx=10, pady=5)
        
    def write_output(self, text, tag='success'):
        """Write text to terminal with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.terminal_output.config(state='normal')
        self.terminal_output.insert('end', f"[{timestamp}] {text}\n", tag)
        self.terminal_output.see('end')
        self.terminal_output.config(state='disabled')
        
    def check_sudo_status(self):
        """Check if running with sudo privileges"""
        if os.geteuid() != 0:
            self.sudo_label.config(text="NO SUDO - LIMITED FEATURES")
            self.write_output("WARNING: Not running as sudo - some features limited", 'warning')
        else:
            self.sudo_label.config(text="SUDO ACTIVE")
            self.write_output("Running with administrator privileges", 'accent')
            
    def toggle_monitoring(self):
        """Toggle system monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.status_label.config(text="MONITORING ACTIVE")
            self.write_output("Starting system monitoring...", 'accent')
            
            thread = threading.Thread(target=self.monitor_system)
            thread.daemon = True
            thread.start()
        else:
            self.monitoring = False
            self.status_label.config(text="MONITORING STOPPED")
            self.write_output("Monitoring stopped", 'warning')
            
    def monitor_system(self):
        """System monitoring loop"""
        while self.monitoring:
            try:
                # Get system stats
                stats = self.collect_system_stats()
                self.output_queue.put(('monitor_display', stats))
                time.sleep(2)
            except Exception as e:
                self.output_queue.put(('monitor_error', str(e)))
                time.sleep(5)
                
    def collect_system_stats(self):
        """Collect comprehensive system statistics"""
        stats = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'cpu_usage': 'N/A',
            'memory': {'used': 'N/A', 'total': 'N/A', 'percent': 'N/A'},
            'power': {'cpu': 'N/A', 'gpu': 'N/A', 'npu': 'N/A'},
            'network': {'up': 'N/A', 'down': 'N/A'},
            'temperature': 'N/A'
        }
        
        # CPU usage
        try:
            stats['cpu_usage'] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
        except:
            pass
            
        # Memory usage
        try:
            mem = psutil.virtual_memory()
            stats['memory'] = {
                'used': self.network_monitor.format_bytes(mem.used),
                'total': self.network_monitor.format_bytes(mem.total),
                'percent': f"{mem.percent:.1f}%"
            }
        except:
            pass
            
        # Power consumption (requires sudo)
        if os.geteuid() == 0:
            power_data = self.silicon_monitor.get_powermetrics_data()
            stats['power'] = {
                'cpu': power_data.get('cpu_power', 'N/A'),
                'gpu': power_data.get('gpu_power', 'N/A'),
                'npu': power_data.get('ane_power', 'N/A')
            }
            
        # Network stats
        try:
            net_stats = self.network_monitor.get_network_stats()
            stats['network'] = {
                'up': net_stats.get('upload_rate', 'N/A'),
                'down': net_stats.get('download_rate', 'N/A')
            }
        except:
            pass
            
        # Temperature (requires sudo)
        if os.geteuid() == 0:
            try:
                result = subprocess.run(['sudo', 'powermetrics', '--samplers', 'smc', '-n', '1'],
                                      capture_output=True, text=True, timeout=3)
                for line in result.stdout.split('\n'):
                    if 'CPU die temperature' in line:
                        stats['temperature'] = line.split(':')[1].strip()
                        break
            except:
                pass
                
        return stats
        
    def display_monitor_stats(self, stats):
        """Display monitoring statistics"""
        display_text = f"""
SYSTEM MONITOR [{stats['timestamp']}]
==========================================
CPU Usage:    {stats['cpu_usage']}
Memory:       {stats['memory']['used']} / {stats['memory']['total']} ({stats['memory']['percent']})
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
        self.write_output(display_text.strip(), 'accent')
        
    def run_cpu_stress(self):
        """Run CPU stress test"""
        if self.stress_testing:
            self.write_output("Stress test already running", 'warning')
            return
            
        self.stress_testing = True
        self.status_label.config(text="CPU STRESS TEST")
        self.write_output("Starting CPU stress test (30 seconds)...", 'warning')
        
        thread = threading.Thread(target=self.cpu_stress_test)
        thread.daemon = True
        thread.start()
        
    def cpu_stress_test(self):
        """CPU stress test implementation"""
        try:
            duration = 30
            cores_to_use = self.silicon_monitor.chip_info['cpu_cores']
            
            self.output_queue.put(('stress_update', f"Utilizing {cores_to_use} CPU cores"))
            
            stop_event = multiprocessing.Event()
            processes = []
            
            for i in range(cores_to_use):
                p = multiprocessing.Process(
                    target=self.stress_engine.cpu_stress_worker,
                    args=(i, duration, stop_event)
                )
                p.start()
                processes.append(p)
            
            # Monitor progress
            for i in range(duration):
                if not self.stress_testing:
                    stop_event.set()
                    break
                self.output_queue.put(('stress_update', f"CPU test progress: {i+1}/{duration} seconds"))
                time.sleep(1)
            
            # Cleanup
            stop_event.set()
            for p in processes:
                p.join(timeout=5)
                if p.is_alive():
                    p.terminate()
            
            self.output_queue.put(('stress_complete', 'CPU stress test completed'))
            
        except Exception as e:
            self.output_queue.put(('stress_error', f"CPU stress test error: {e}"))
        finally:
            self.stress_testing = False
            
    def run_memory_stress(self):
        """Run memory stress test"""
        if self.stress_testing:
            self.write_output("Stress test already running", 'warning')
            return
            
        self.stress_testing = True
        self.status_label.config(text="MEMORY STRESS TEST")
        self.write_output("Starting memory stress test...", 'warning')
        
        thread = threading.Thread(target=self.memory_stress_test)
        thread.daemon = True
        thread.start()
        
    def memory_stress_test(self):
        """Memory stress test implementation"""
        try:
            available_mb = psutil.virtual_memory().available // (1024 * 1024)
            target_mb = min(available_mb // 2, 1000)  # Use half available or 1GB max
            
            self.output_queue.put(('stress_update', f"Allocating {target_mb}MB of memory"))
            
            result = self.stress_engine.memory_stress_worker(target_mb)
            
            self.output_queue.put(('stress_complete', f"Memory test completed - allocated {result}MB"))
            
        except Exception as e:
            self.output_queue.put(('stress_error', f"Memory stress test error: {e}"))
        finally:
            self.stress_testing = False
            
    def run_optimization(self):
        """Run system optimization"""
        self.status_label.config(text="OPTIMIZING SYSTEM")
        self.write_output("Starting system optimization...", 'accent')
        
        thread = threading.Thread(target=self.optimization_thread)
        thread.daemon = True
        thread.start()
        
    def optimization_thread(self):
        """System optimization implementation"""
        if os.geteuid() == 0:
            # Commands for sudo mode
            commands = [
                ("Clearing DNS cache", "dscacheutil -flushcache && killall -HUP mDNSResponder"),
                ("Purging inactive memory", "purge"),
                ("Enabling high performance mode", "pmset -a highpowermode 1"),
                ("Disabling sleep", "pmset -a sleep 0"),
                ("Clearing system caches", "rm -rf /System/Library/Caches/* 2>/dev/null || true"),
                ("Rebuilding font cache", "atsutil databases -removeUser && atsutil server -shutdown && atsutil server -ping")
            ]
        else:
            # Commands for non-sudo mode (user-level optimizations)
            commands = [
                ("Clearing user DNS cache", "dscacheutil -flushcache"),
                ("Clearing user caches", "rm -rf ~/Library/Caches/com.apple.* 2>/dev/null || true"),
                ("Clearing user font cache", "atsutil databases -removeUser"),
                ("Optimizing user preferences", "defaults write com.apple.dock persistent-apps -array && killall Dock"),
                ("Clearing user logs", "rm -rf ~/Library/Logs/* 2>/dev/null || true"),
                ("Restarting user services", "launchctl kickstart -k gui/$(id -u)/com.apple.Dock")
            ]
        
        for description, cmd in commands:
            self.output_queue.put(('optimize_step', (description, cmd)))
            time.sleep(1)
        
        self.output_queue.put(('optimize_complete', 'System optimization completed'))
        
    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal_output.config(state='normal')
        self.terminal_output.delete(1.0, 'end')
        self.terminal_output.config(state='disabled')
        self.write_output("Terminal cleared", 'accent')
        
    def quit_app(self):
        """Quit application"""
        self.monitoring = False
        self.stress_testing = False
        self.write_output("Shutting down GerdsenAI OptiMac...", 'warning')
        self.root.after(1000, self.root.quit)
        
    def start_queue_processor(self):
        """Start queue processor for thread communication"""
        self.process_queue()
        
    def process_queue(self):
        """Process messages from background threads"""
        try:
            while True:
                msg_type, msg_data = self.output_queue.get_nowait()
                
                if msg_type == 'monitor_display':
                    self.display_monitor_stats(msg_data)
                elif msg_type == 'monitor_error':
                    self.write_output(f"Monitor error: {msg_data}", 'error')
                elif msg_type == 'stress_update':
                    self.write_output(msg_data, 'warning')
                elif msg_type == 'stress_complete':
                    self.write_output(msg_data, 'accent')
                    self.status_label.config(text="READY")
                elif msg_type == 'stress_error':
                    self.write_output(msg_data, 'error')
                    self.status_label.config(text="ERROR")
                elif msg_type == 'optimize_step':
                    description, cmd = msg_data
                    self.command_executor.execute_command(cmd, description)
                elif msg_type == 'optimize_complete':
                    self.write_output(msg_data, 'accent')
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
        import psutil
    except ImportError:
        print("ERROR: psutil module required. Install with: pip install psutil")
        sys.exit(1)
    
    # Create and run application
    root = tk.Tk()
    app = GerdsenAIOptiMac(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)

if __name__ == "__main__":
    main()
