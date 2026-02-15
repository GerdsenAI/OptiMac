#!/usr/bin/env python3
"""
Live MCP Tool Test Runner with Before/After System Monitoring.

Calls each SAFE MCP tool via the MCP protocol, captures system state
before and after each call, and writes results to test_results.md.

Skips: network tools, sudo-requiring tools, destructive tools.
"""

import asyncio
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient

# ── Safe tools to test (no sudo, no network, no destructive) ──────────
SAFE_TOOLS = [
    # System Monitoring (all read-only)
    {"name": "optimac_system_overview", "args": {}, "category": "System Monitoring"},
    {"name": "optimac_memory_status", "args": {}, "category": "System Monitoring"},
    {
        "name": "optimac_top_processes",
        "args": {"limit": 5},
        "category": "System Monitoring",
    },
    {"name": "optimac_disk_usage", "args": {}, "category": "System Monitoring"},
    {"name": "optimac_power_settings", "args": {}, "category": "System Monitoring"},
    {"name": "optimac_battery_health", "args": {}, "category": "System Monitoring"},
    {"name": "optimac_io_stats", "args": {}, "category": "System Monitoring"},
    # Security (read-only audits)
    {"name": "optimac_sec_status", "args": {}, "category": "Security"},
    {
        "name": "optimac_sec_firewall",
        "args": {"action": "status"},
        "category": "Security",
    },
    {"name": "optimac_sec_audit_ports", "args": {}, "category": "Security"},
    {"name": "optimac_sec_audit_malware", "args": {}, "category": "Security"},
    {
        "name": "optimac_sec_audit_unsigned",
        "args": {"limit": 10},
        "category": "Security",
    },
    {"name": "optimac_sec_audit_connections", "args": {}, "category": "Security"},
    # AI Stack (read-only checks)
    {"name": "optimac_ai_stack_status", "args": {}, "category": "AI Stack"},
    {
        "name": "optimac_ollama_models",
        "args": {"action": "list"},
        "category": "AI Stack",
    },
    {"name": "optimac_gpu_stats", "args": {}, "category": "AI Stack"},
    {"name": "optimac_models_running", "args": {}, "category": "AI Stack"},
    {"name": "optimac_models_available", "args": {}, "category": "AI Stack"},
    # Config (read-only)
    {
        "name": "optimac_config_get",
        "args": {"key": "protectedProcesses"},
        "category": "Config",
    },
    # System misc (read-only)
    {"name": "optimac_sys_login_items", "args": {}, "category": "System Misc"},
    {"name": "optimac_watchdog_status", "args": {}, "category": "System Misc"},
    {"name": "optimac_memory_pressure_check", "args": {}, "category": "System Misc"},
]


def get_system_snapshot():
    """Capture current system state: memory, CPU, swap."""
    snapshot = {}

    # Memory via vm_stat
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
        lines = vm.stdout.strip().split("\n")
        page_size = 16384  # Apple Silicon default
        for line in lines:
            if "page size" in line.lower():
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        page_size = int(p)
                        break

        stats = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                val = val.strip().rstrip(".")
                if val.isdigit():
                    stats[key.strip()] = int(val) * page_size

        free = stats.get("Pages free", 0)
        active = stats.get("Pages active", 0)
        inactive = stats.get("Pages inactive", 0)
        speculative = stats.get("Pages speculative", 0)
        wired = stats.get("Pages wired down", 0)
        compressed = stats.get("Pages occupied by compressor", 0)
        purgeable = stats.get("Pages purgeable", 0)

        total_bytes = int(
            subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )

        used = active + wired + compressed
        snapshot["memory"] = {
            "total_gb": round(total_bytes / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "inactive_gb": round(inactive / (1024**3), 2),
            "purgeable_gb": round(purgeable / (1024**3), 2),
            "compressed_gb": round(compressed / (1024**3), 2),
            "wired_gb": round(wired / (1024**3), 2),
            "pressure_pct": round(used / total_bytes * 100, 1),
        }
    except Exception as e:
        snapshot["memory"] = {"error": str(e)}

    # Swap
    try:
        swap = subprocess.run(
            ["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, timeout=5
        )
        snapshot["swap"] = swap.stdout.strip()
    except Exception as e:
        snapshot["swap"] = f"error: {e}"

    # Load average
    try:
        load = subprocess.run(
            ["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True, timeout=5
        )
        snapshot["load_avg"] = load.stdout.strip()
    except Exception as e:
        snapshot["load_avg"] = f"error: {e}"

    return snapshot


def format_snapshot(snap, label=""):
    """Format snapshot to readable string."""
    lines = []
    if label:
        lines.append(f"**{label}**")

    mem = snap.get("memory", {})
    if "error" not in mem:
        lines.append(
            f"  Memory: {mem['used_gb']}GB used / {mem['total_gb']}GB total "
            f"({mem['pressure_pct']}% pressure) | "
            f"Free: {mem['free_gb']}GB | Inactive: {mem['inactive_gb']}GB | "
            f"Purgeable: {mem['purgeable_gb']}GB | Compressed: {mem['compressed_gb']}GB"
        )
    else:
        lines.append(f"  Memory: {mem['error']}")

    lines.append(f"  Swap: {snap.get('swap', 'N/A')}")
    lines.append(f"  Load: {snap.get('load_avg', 'N/A')}")
    return "\n".join(lines)


def diff_snapshot(before, after):
    """Compare two snapshots and return delta string."""
    deltas = []

    bm = before.get("memory", {})
    am = after.get("memory", {})

    if "error" not in bm and "error" not in am:
        used_delta = round(am["used_gb"] - bm["used_gb"], 3)
        free_delta = round(am["free_gb"] - bm["free_gb"], 3)
        pressure_delta = round(am["pressure_pct"] - bm["pressure_pct"], 1)

        sign = lambda v: f"+{v}" if v > 0 else str(v)
        deltas.append(
            f"  Δ Used: {sign(used_delta)}GB | Δ Free: {sign(free_delta)}GB | "
            f"Δ Pressure: {sign(pressure_delta)}%"
        )

    return "\n".join(deltas) if deltas else "  (no measurable change)"


async def run_tests():
    """Run all safe MCP tools with monitoring."""

    # Find the MCP server
    server_dir = Path(__file__).parent.parent / "optimac-mcp-server"
    node_cmd = "node"
    server_script = str(server_dir / "dist" / "index.js")

    if not Path(server_script).exists():
        print(f"ERROR: Server not built. Run 'npm run build' in {server_dir}")
        return

    # Create MCP client
    client = MCPClient(
        {
            "name": "optimac",
            "type": "stdio",
            "command": node_cmd,
            "args": [server_script],
        }
    )

    print("Connecting to MCP server...")
    connected = await client.connect()
    if not connected:
        print("ERROR: Could not connect to MCP server")
        return

    # List tools to verify
    tools = await client.list_tools()
    tool_names = {t["name"] for t in tools}
    print(f"Connected! Server has {len(tools)} tools registered.\n")

    # Results collection
    results = []
    overall_start = time.time()
    baseline = get_system_snapshot()

    print(f"{'='*70}")
    print(f"  BASELINE SYSTEM STATE")
    print(f"{'='*70}")
    print(format_snapshot(baseline))
    print()

    # Run each tool
    for i, tool in enumerate(SAFE_TOOLS):
        name = tool["name"]
        args = tool["args"]
        category = tool["category"]

        # Check if tool exists
        if name not in tool_names:
            results.append(
                {
                    "name": name,
                    "category": category,
                    "status": "SKIP",
                    "reason": "not registered",
                    "duration": 0,
                    "output": "",
                    "delta": "",
                }
            )
            print(f"[{i+1:2}/{len(SAFE_TOOLS)}] ⏭  {name} — NOT REGISTERED")
            continue

        # Before snapshot
        before = get_system_snapshot()

        # Execute tool
        print(f"[{i+1:2}/{len(SAFE_TOOLS)}] 🔄 {name}", end="", flush=True)
        start = time.time()

        try:
            result = await asyncio.wait_for(
                client.execute_tool(name, args), timeout=30.0
            )
            duration = round(time.time() - start, 2)

            is_error = result.get("isError", False)
            content = result.get("content", [])
            output_text = ""
            for c in content:
                if c.get("type") == "text":
                    output_text += c.get("text", "")

            # After snapshot
            after = get_system_snapshot()
            delta = diff_snapshot(before, after)

            status = "FAIL" if is_error else "PASS"
            symbol = "❌" if is_error else "✅"

            # Truncate output for display
            display_out = output_text[:120].replace("\n", " ")
            print(
                f"\r[{i+1:2}/{len(SAFE_TOOLS)}] {symbol} {name} ({duration}s) — {display_out}..."
            )

            results.append(
                {
                    "name": name,
                    "category": category,
                    "status": status,
                    "reason": "",
                    "duration": duration,
                    "output": output_text,
                    "delta": delta,
                    "before": before,
                    "after": after,
                }
            )

        except asyncio.TimeoutError:
            duration = round(time.time() - start, 2)
            print(f"\r[{i+1:2}/{len(SAFE_TOOLS)}] ⏰ {name} ({duration}s) — TIMEOUT")
            results.append(
                {
                    "name": name,
                    "category": category,
                    "status": "TIMEOUT",
                    "reason": "30s timeout exceeded",
                    "duration": duration,
                    "output": "",
                    "delta": "",
                }
            )
        except Exception as e:
            duration = round(time.time() - start, 2)
            print(f"\r[{i+1:2}/{len(SAFE_TOOLS)}] ❌ {name} ({duration}s) — ERROR: {e}")
            results.append(
                {
                    "name": name,
                    "category": category,
                    "status": "ERROR",
                    "reason": str(e),
                    "duration": duration,
                    "output": "",
                    "delta": "",
                }
            )

    # Final snapshot
    final = get_system_snapshot()
    overall_duration = round(time.time() - overall_start, 1)

    # Disconnect
    await client.disconnect()

    # ── Write results to markdown ─────────────────────────────────────
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] in ("ERROR", "TIMEOUT"))
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    md = []
    md.append(f"# OptiMac MCP Live Test Results")
    md.append(f"")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Duration:** {overall_duration}s")
    md.append(
        f"**Tools Tested:** {len(SAFE_TOOLS)} (safe, non-network, non-destructive)"
    )
    md.append(f"**Server Tools Available:** {len(tools)}")
    md.append(f"")
    md.append(f"## Summary")
    md.append(f"| Status | Count |")
    md.append(f"|--------|-------|")
    md.append(f"| ✅ PASS | {passed} |")
    md.append(f"| ❌ FAIL | {failed} |")
    md.append(f"| ⏰ TIMEOUT/ERROR | {errors} |")
    md.append(f"| ⏭ SKIP | {skipped} |")
    md.append(f"")

    md.append(f"## System State")
    md.append(f"")
    md.append(f"### Baseline (Before Tests)")
    md.append(f"```")
    md.append(format_snapshot(baseline, "Start"))
    md.append(f"```")
    md.append(f"")
    md.append(f"### Final (After All Tests)")
    md.append(f"```")
    md.append(format_snapshot(final, "End"))
    md.append(f"```")
    md.append(f"")
    md.append(f"### Overall Delta")
    md.append(f"```")
    md.append(diff_snapshot(baseline, final))
    md.append(f"```")
    md.append(f"")

    # Per-category results
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    for cat, cat_results in categories.items():
        md.append(f"## {cat}")
        md.append(f"")

        for r in cat_results:
            status_icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "TIMEOUT": "⏰",
                "ERROR": "⚠️",
                "SKIP": "⏭",
            }.get(r["status"], "❓")
            md.append(
                f"### {status_icon} `{r['name']}` — {r['status']} ({r['duration']}s)"
            )

            if r.get("reason"):
                md.append(f"**Reason:** {r['reason']}")

            if r.get("delta"):
                md.append(f"**System Impact:**")
                md.append(f"```")
                md.append(r["delta"])
                md.append(f"```")

            if r.get("output"):
                # Truncate very long outputs
                out = r["output"]
                if len(out) > 1500:
                    out = out[:1500] + "\n... (truncated)"
                md.append(f"<details><summary>Output</summary>")
                md.append(f"")
                md.append(f"```json")
                md.append(out)
                md.append(f"```")
                md.append(f"</details>")

            md.append(f"")

    # Write file
    results_path = Path(__file__).parent / "test_results.md"
    results_path.write_text("\n".join(md))
    print(f"\n{'='*70}")
    print(f"  Results written to: {results_path}")
    print(f"  {passed} passed, {failed} failed, {errors} errors, {skipped} skipped")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(run_tests())
