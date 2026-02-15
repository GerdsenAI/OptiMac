#!/usr/bin/env python3
"""
Comprehensive OptiMac MCP Server Test Suite
Tests all 61 tools with prerequisite checks and detailed reporting.

Parameter names match the Zod schemas in optimac-mcp-server/src/tools/*.ts exactly.
"""

import asyncio
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient

# Paths used by test fixtures
HOME = os.path.expanduser("~")
REPO_PATH = str(Path(__file__).parent.parent)  # OptiMac repo root
TEST_FILE = str(Path(__file__).parent / "scratch_test.txt")  # temp file for edit tests

# All 61 tools organized by category with metadata.
# 'args' must use the exact parameter names from the server's Zod inputSchema.
TOOL_DEFINITIONS = {
    # ── SYSTEM MONITORING ─────────────────────────────────────────────
    "system_monitoring": [
        {"name": "optimac_memory_status", "safe": True, "sudo": False, "args": {}},
        {
            "name": "optimac_top_processes",
            "safe": True,
            "sudo": False,
            "args": {"limit": 10},
        },
        {"name": "optimac_disk_usage", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_thermal_status", "safe": True, "sudo": True, "args": {}},
        {"name": "optimac_power_settings", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_system_overview", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_battery_health", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_io_stats", "safe": True, "sudo": False, "args": {}},
    ],
    # ── SYSTEM CONTROL ────────────────────────────────────────────────
    "system_control": [
        {"name": "optimac_purge_memory", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_flush_dns", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_flush_routes", "safe": False, "sudo": True, "args": {}},
        {
            "name": "optimac_set_power",
            "safe": False,
            "sudo": True,
            "args": {"setting": "sleep", "value": "0"},
        },
        {"name": "optimac_power_optimize", "safe": False, "sudo": True, "args": {}},
        # Uses our own PID — tool will find the process and either send TERM or refuse (protected)
        {
            "name": "optimac_kill_process",
            "safe": False,
            "sudo": False,
            "args": {"pid": os.getpid(), "force": False},
        },
        {
            "name": "optimac_disable_service",
            "safe": False,
            "sudo": True,
            "args": {"service": "com.apple.Spotlight"},
        },
        {
            "name": "optimac_enable_service",
            "safe": False,
            "sudo": True,
            "args": {"service": "com.apple.Spotlight"},
        },
        {"name": "optimac_disable_spotlight", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_clear_caches", "safe": False, "sudo": True, "args": {}},
        {
            "name": "optimac_set_dns",
            "safe": False,
            "sudo": True,
            "args": {"preset": "cloudflare"},
        },
        {"name": "optimac_network_reset", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_reduce_ui_overhead", "safe": False, "sudo": True, "args": {}},
        {
            "name": "optimac_nvram_perf_mode",
            "safe": False,
            "sudo": True,
            "args": {"enable": True},
        },
        {"name": "optimac_sys_login_items", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_sys_eject", "safe": False, "sudo": False, "args": {}},
        {"name": "optimac_sys_lock", "safe": False, "sudo": False, "args": {}},
        {
            "name": "optimac_sys_restart_service",
            "safe": False,
            "sudo": False,
            "args": {"service": "Dock"},
        },
        {"name": "optimac_sys_trash", "safe": False, "sudo": False, "args": {}},
        {
            "name": "optimac_power_profile",
            "safe": False,
            "sudo": True,
            "args": {"profile": "balanced"},
        },
        {"name": "optimac_debloat_reenable", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_rebuild_spotlight", "safe": False, "sudo": True, "args": {}},
        {"name": "optimac_optimize_homebrew", "safe": False, "sudo": False, "args": {}},
    ],
    # ── AI STACK ──────────────────────────────────────────────────────
    "ai_stack": [
        {"name": "optimac_ai_stack_status", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_ollama_start", "safe": False, "sudo": False, "args": {}},
        {"name": "optimac_ollama_stop", "safe": False, "sudo": False, "args": {}},
        {
            "name": "optimac_ollama_models",
            "safe": True,
            "sudo": False,
            "args": {"action": "list"},
        },
        {
            "name": "optimac_mlx_serve",
            "safe": False,
            "sudo": False,
            "args": {"model": "mlx-model"},
            "requires": "mlx",
        },
        {"name": "optimac_mlx_stop", "safe": False, "sudo": False, "args": {}},
        {
            "name": "optimac_swap_model",
            "safe": False,
            "sudo": False,
            "args": {"runtime": "ollama", "model": "test"},
        },
        {"name": "optimac_gpu_stats", "safe": True, "sudo": True, "args": {}},
        {
            "name": "optimac_model_benchmark",
            "safe": False,
            "sudo": False,
            "args": {"model": "llama3.2", "prompt": "test"},
        },
        {
            "name": "optimac_mlx_quantize",
            "safe": False,
            "sudo": False,
            "args": {"model": "test-model"},
        },
    ],
    # ── MODEL MANAGEMENT ──────────────────────────────────────────────
    "model_management": [
        {"name": "optimac_models_available", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_ollama_available", "safe": True, "sudo": False, "args": {}},
        {
            "name": "optimac_model_serve",
            "safe": False,
            "sudo": False,
            "args": {"runtime": "ollama", "model": "test"},
        },
        {
            "name": "optimac_model_unload",
            "safe": False,
            "sudo": False,
            "args": {"runtime": "ollama"},
        },
        {"name": "optimac_models_running", "safe": True, "sudo": False, "args": {}},
        # ── FIXED: was "directory" → correct param is "path"
        {
            "name": "optimac_model_dir_set",
            "safe": False,
            "sudo": False,
            "args": {"path": "/tmp/models"},
        },
        {"name": "optimac_model_dir_get", "safe": True, "sudo": False, "args": {}},
        # ── FIXED: was "model"+"sizeGB" → correct params are "size_gb" (required) + "model_name" (optional)
        {
            "name": "optimac_model_ram_check",
            "safe": True,
            "sudo": False,
            "args": {"size_gb": 4, "model_name": "test-model"},
        },
        {
            "name": "optimac_model_chat",
            "safe": False,
            "sudo": False,
            "args": {"prompt": "Hello"},
        },
    ],
    # ── MODEL TASKS ───────────────────────────────────────────────────
    "model_tasks": [
        {
            "name": "optimac_model_task",
            "safe": False,
            "sudo": False,
            "args": {"task": "Test task"},
        },
        # ── FIXED: was empty → required param "repo_path"
        {
            "name": "optimac_model_code_review",
            "safe": False,
            "sudo": False,
            "args": {"repo_path": REPO_PATH},
        },
        # ── FIXED: was {"description":"Test"} → requires both "description" AND "output_path"
        {
            "name": "optimac_model_generate",
            "safe": False,
            "sudo": False,
            "args": {
                "description": "Generate a hello-world TypeScript function",
                "output_path": f"{HOME}/tmp/optimac_test_gen.ts",
            },
        },
        # ── FIXED: was "file"/"instruction" → correct params are "file_path" / "instructions"
        {
            "name": "optimac_model_edit",
            "safe": False,
            "sudo": False,
            "args": {
                "file_path": TEST_FILE,
                "instructions": "Add a comment at the top saying this is a test file",
            },
            "setup": "create_scratch_file",
        },
        # ── FIXED: was "files" → correct param is "paths" (array)
        {
            "name": "optimac_model_summarize",
            "safe": False,
            "sudo": False,
            "args": {
                "paths": [f"{REPO_PATH}/README.md"],
            },
        },
        # ── FIXED: was empty → required param "repo_path"
        {
            "name": "optimac_model_commit",
            "safe": False,
            "sudo": False,
            "args": {
                "repo_path": REPO_PATH,
                "auto_commit": True,
            },
        },
        # ── FIXED: was "task"/"provider" → required param is "prompt"
        {
            "name": "optimac_cloud_escalate",
            "safe": False,
            "sudo": False,
            "args": {
                "prompt": "What is 2+2?",
                "provider": "openrouter",
            },
        },
        # ── FIXED: was "task"/"endpoint" → correct params are "prompt" / "edge_endpoint"
        {
            "name": "optimac_edge_escalate",
            "safe": False,
            "sudo": False,
            "args": {
                "prompt": "What is 2+2?",
                "edge_endpoint": "test-edge",
            },
        },
        {
            "name": "optimac_model_route",
            "safe": False,
            "sudo": False,
            "args": {"task": "Test"},
        },
    ],
    # ── EDGE TOOLS ────────────────────────────────────────────────────
    # Order matters: add → test → list → remove (so test has a live endpoint)
    "edge_tools": [
        {
            "name": "optimac_edge_add",
            "safe": False,
            "sudo": False,
            "args": {
                "name": "test-edge",
                "url": "http://localhost:8080",
                "runtime": "ollama",
            },
        },
        # ── FIXED ordering: test BEFORE remove so the endpoint still exists
        {
            "name": "optimac_edge_test",
            "safe": False,
            "sudo": False,
            "args": {"name": "test-edge"},
        },
        {"name": "optimac_edge_list", "safe": True, "sudo": False, "args": {}},
        {
            "name": "optimac_edge_remove",
            "safe": False,
            "sudo": False,
            "args": {"name": "test-edge"},
        },
    ],
    # ── MEMORY PRESSURE ───────────────────────────────────────────────
    "memory_pressure": [
        {
            "name": "optimac_memory_pressure_check",
            "safe": True,
            "sudo": False,
            "args": {"dry_run": True},
        },
        {
            "name": "optimac_maintenance_cycle",
            "safe": False,
            "sudo": True,
            "args": {"dry_run": True},
        },
    ],
    # ── CONFIGURATION ─────────────────────────────────────────────────
    "configuration": [
        {"name": "optimac_config_get", "safe": True, "sudo": False, "args": {}},
        # ── FIXED: was {"key":"testKey","value":"testValue"} →
        #    key must be an enum, value must match type (number for thresholds)
        {
            "name": "optimac_config_set",
            "safe": False,
            "sudo": False,
            "args": {
                "key": "memoryWarningThreshold",
                "value": 0.75,
            },
        },
        # ── FIXED: was "process" → correct param is "process_name"
        {
            "name": "optimac_config_protect_process",
            "safe": False,
            "sudo": False,
            "args": {
                "process_name": "test-process",
            },
        },
        {
            "name": "optimac_config_unprotect_process",
            "safe": False,
            "sudo": False,
            "args": {
                "process_name": "test-process",
            },
        },
        {
            "name": "optimac_config_set_port",
            "safe": False,
            "sudo": False,
            "args": {
                "service": "ollama",
                "port": 11434,
            },
        },
        {
            "name": "optimac_debloat",
            "safe": False,
            "sudo": True,
            "args": {
                "preset": "minimal",
            },
        },
    ],
    # ── AUTONOMY ──────────────────────────────────────────────────────
    "autonomy": [
        {"name": "optimac_watchdog_start", "safe": False, "sudo": False, "args": {}},
        {"name": "optimac_watchdog_stop", "safe": False, "sudo": False, "args": {}},
        {"name": "optimac_watchdog_status", "safe": True, "sudo": False, "args": {}},
    ],
    # ── NETWORK TOOLS (NEW) ───────────────────────────────────────────
    "network_tools": [
        {
            "name": "optimac_net_connections",
            "safe": True,
            "sudo": False,
            "args": {"filter": "listen", "limit": 5},
        },
        {"name": "optimac_net_info", "safe": True, "sudo": False, "args": {}},
        {
            "name": "optimac_net_ping",
            "safe": False,
            "sudo": False,
            "args": {"host": "127.0.0.1", "count": 1},
        },
        {"name": "optimac_net_speedtest", "safe": False, "sudo": False, "args": {}},
        {
            "name": "optimac_net_wifi",
            "safe": False,
            "sudo": False,
            "args": {"action": "status"},
        },
        {
            "name": "optimac_net_bluetooth",
            "safe": False,
            "sudo": False,
            "args": {"action": "status"},
        },
        {
            "name": "optimac_net_wol",
            "safe": False,
            "sudo": False,
            "args": {"mac": "00:11:22:33:44:55"},
        },
    ],
    # ── SECURITY TOOLS (NEW) ──────────────────────────────────────────
    "security_tools": [
        {"name": "optimac_sec_status", "safe": True, "sudo": False, "args": {}},
        {
            "name": "optimac_sec_firewall",
            "safe": False,
            "sudo": True,
            "args": {"action": "status"},
        },
        {"name": "optimac_sec_audit_ports", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_sec_audit_malware", "safe": True, "sudo": False, "args": {}},
        {"name": "optimac_sec_audit_auth", "safe": True, "sudo": True, "args": {}},
        {
            "name": "optimac_sec_audit_unsigned",
            "safe": True,
            "sudo": False,
            "args": {"limit": 10},
        },
        {
            "name": "optimac_sec_audit_connections",
            "safe": True,
            "sudo": False,
            "args": {},
        },
    ],
}


class MCPTester:
    def __init__(self):
        self.results = []
        self.client = None
        self.has_sudo = False
        self.has_ollama = False
        self.has_mlx = False

    async def check_prerequisites(self):
        """Check system prerequisites"""
        # Check sudo
        result = subprocess.run(["sudo", "-n", "true"], capture_output=True)
        self.has_sudo = result.returncode == 0

        # Check Ollama
        result = subprocess.run(["which", "ollama"], capture_output=True)
        self.has_ollama = result.returncode == 0

        # Check MLX (simplified)
        result = subprocess.run(["pip3", "list"], capture_output=True, text=True)
        self.has_mlx = "mlx-lm" in result.stdout

        print(
            f"Prerequisites: sudo={self.has_sudo}, ollama={self.has_ollama}, mlx={self.has_mlx}"
        )

    def run_setup(self, setup_name: str):
        """Run a named setup action before a test"""
        if setup_name == "create_scratch_file":
            Path(TEST_FILE).write_text(
                "// scratch test file for optimac_model_edit\nconsole.log('hello');\n"
            )

    async def test_tool(self, tool_def):
        """Test a single tool"""
        name = tool_def["name"]
        args = tool_def.get("args", {})
        requires_sudo = tool_def.get("sudo", False)
        requires_dep = tool_def.get("requires", None)

        # Check prerequisites
        skip_reason = None
        if requires_sudo and not self.has_sudo:
            skip_reason = "Requires sudo (passwordless not configured)"
        elif requires_dep == "mlx" and not self.has_mlx:
            skip_reason = "Requires MLX (mlx-lm not installed)"

        if skip_reason:
            print(f"  SKIP: {name} - {skip_reason}")
            return {
                "tool": name,
                "status": "SKIP",
                "reason": skip_reason,
                "durationMs": 0,
            }

        # Run any pre-test setup
        if "setup" in tool_def:
            self.run_setup(tool_def["setup"])

        # Test the tool
        print(f"  Testing {name}...", end=" ", flush=True)
        start = datetime.now()

        try:
            result = await self.client.execute_tool(name, args)
            duration = (datetime.now() - start).total_seconds() * 1000

            # Check if result indicates error
            if isinstance(result, dict) and result.get("isError"):
                print("FAIL")
                # Extract error message from content if present
                error_text = "Unknown error"
                if result.get("content"):
                    for content in result["content"]:
                        if content.get("type") == "text":
                            error_text = content.get("text", "Unknown error")
                            break
                return {
                    "tool": name,
                    "status": "FAIL",
                    "reason": error_text,
                    "durationMs": duration,
                    "output": result,
                }
            else:
                print("PASS")
                return {
                    "tool": name,
                    "status": "PASS",
                    "durationMs": duration,
                    "output": str(result)[:200] if result else "",
                }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            error_msg = str(e)[:100]
            print(f"ERROR: {error_msg}")
            return {
                "tool": name,
                "status": "ERROR",
                "reason": str(e),
                "durationMs": duration,
            }

    async def run_all_tests(self):
        """Run comprehensive test suite"""
        # Ensure tmp dir exists for generate tests
        os.makedirs(f"{HOME}/tmp", exist_ok=True)

        # Setup MCP client
        config = {
            "name": "optimac",
            "type": "stdio",
            "command": "node",
            "args": [
                "/Users/gerdsenai/Documents/OptiMac/optimac-mcp-server/dist/index.js"
            ],
        }

        self.client = MCPClient(config)

        print("Connecting to OptiMac MCP Server...")
        try:
            await self.client.connect()
            print("✓ Connected\n")
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return

        # Check prerequisites
        await self.check_prerequisites()
        print()

        # Test all tools by category
        for category, tools in TOOL_DEFINITIONS.items():
            print(f"=== {category.upper().replace('_', ' ')} ({len(tools)} tools) ===")
            for tool_def in tools:
                result = await self.test_tool(tool_def)
                self.results.append(result)
            print()

        await self.client.disconnect()

        # Cleanup scratch file
        try:
            Path(TEST_FILE).unlink(missing_ok=True)
            Path(f"{TEST_FILE}.bak").unlink(missing_ok=True)
        except OSError:
            pass

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate markdown and JSON reports"""
        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "PASS"),
            "failed": sum(1 for r in self.results if r["status"] == "FAIL"),
            "skipped": sum(1 for r in self.results if r["status"] == "SKIP"),
            "error": sum(1 for r in self.results if r["status"] == "ERROR"),
        }

        # JSON report
        json_output = {
            "testDate": datetime.now().isoformat(),
            "summary": summary,
            "results": self.results,
        }

        json_path = Path(__file__).parent / "test_results.json"
        with open(json_path, "w") as f:
            json.dump(json_output, f, indent=2)

        # Markdown report
        md = f"""# OptiMac MCP Server Test Results

**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Tools:** {summary['total']}
**Status:** ✅ {summary['passed']} PASS | ❌ {summary['failed']} FAIL | ⏭️ {summary['skipped']} SKIP | ⚠️ {summary['error']} ERROR

## Summary by Category

"""

        # Group by category
        for category, tools in TOOL_DEFINITIONS.items():
            cat_results = [
                r for r in self.results if any(t["name"] == r["tool"] for t in tools)
            ]
            cat_pass = sum(1 for r in cat_results if r["status"] == "PASS")
            cat_total = len(cat_results)

            md += f"### {category.upper().replace('_', ' ')} ({cat_pass}/{cat_total} passed)\n\n"
            md += "| Tool | Status | Duration | Notes |\n"
            md += "|------|--------|----------|-------|\n"

            for result in cat_results:
                status_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "ERROR": "⚠️"}[
                    result["status"]
                ]
                duration = (
                    f"{result['durationMs']:.0f}ms" if result["durationMs"] > 0 else "-"
                )
                reason = result.get("reason", "")[:50]
                md += f"| `{result['tool']}` | {status_icon} {result['status']} | {duration} | {reason} |\n"

            md += "\n"

        # Failed tests detail
        failed = [r for r in self.results if r["status"] in ["FAIL", "ERROR"]]
        if failed:
            md += "## Failed Tests Detail\n\n"
            for r in failed:
                md += f"### {r['tool']}\n"
                md += f"- **Status:** {r['status']}\n"
                md += f"- **Reason:** {r.get('reason', 'Unknown')}\n\n"

        md_path = Path(__file__).parent / "test_results.md"
        with open(md_path, "w") as f:
            f.write(md)

        print(f"\n{'='*60}")
        print(f"Test Results Summary:")
        print(f"  PASS:    {summary['passed']:3d}")
        print(f"  FAIL:    {summary['failed']:3d}")
        print(f"  SKIP:    {summary['skipped']:3d}")
        print(f"  ERROR:   {summary['error']:3d}")
        print(f"  TOTAL:   {summary['total']:3d}")
        print(f"{'='*60}")
        print(f"\n✓ Reports saved:")
        print(f"  - {json_path}")
        print(f"  - {md_path}")


if __name__ == "__main__":
    tester = MCPTester()
    asyncio.run(tester.run_all_tests())
