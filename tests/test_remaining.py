#!/usr/bin/env python3
"""
Manually test ALL remaining MCP tools (excluding network & already-tested).
Each tool is called individually via MCP JSON-RPC with before/after monitoring.
"""

import asyncio
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient


def mem():
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
    total = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True
        ).stdout.strip()
    )
    page = 16384
    stats = {}
    for line in vm.split("\n")[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip().rstrip(".")
            if v.isdigit():
                stats[k.strip()] = int(v) * page
    used = (
        stats.get("Pages active", 0)
        + stats.get("Pages wired down", 0)
        + stats.get("Pages occupied by compressor", 0)
    ) / (1024**2)
    total_mb = total / (1024**2)
    return round(used), round(total_mb), round(used / total_mb * 100, 1)


# ── TOOLS TO TEST ──────────────────────────────────────────────────────
# Format: (name, args, category, notes)
# Skip: network tools, already-tested tools, and truly destructive ones

TOOLS = [
    # ── SYSTEM MONITORING (untested) ──
    ("optimac_thermal_status", {}, "SysMon", "Thermal sensors/throttle state"),
    # ── SECURITY (untested) ──
    ("optimac_sec_audit_auth", {}, "Security", "Auth mechanism audit"),
    # ── SYSTEM CONTROL (read/safe) ──
    (
        "optimac_nvram_perf_mode",
        {"action": "status"},
        "SysCtrl",
        "Check server perf mode NVRAM flag — read only",
    ),
    (
        "optimac_sys_eject",
        {"volume": "__test_nonexistent__"},
        "SysCtrl",
        "Eject non-existent volume — tests error handling",
    ),
    (
        "optimac_sys_trash",
        {"path": "/tmp/__optimac_test_trash__"},
        "SysCtrl",
        "Trash non-existent file — tests error handling",
    ),
    # ── CONFIG ──
    (
        "optimac_config_set",
        {"key": "testKey", "value": "testValue"},
        "Config",
        "Set a test config key",
    ),
    ("optimac_config_get", {}, "Config", "Read config to verify testKey"),
    (
        "optimac_config_set",
        {"key": "testKey", "value": ""},
        "Config",
        "Clean up test key",
    ),
    # ── MODEL MANAGEMENT ──
    (
        "optimac_ollama_available",
        {},
        "ModelMgmt",
        "List models available to download from Ollama",
    ),
    ("optimac_model_dir_get", {}, "ModelMgmt", "Get current model directory"),
    (
        "optimac_model_ram_check",
        {"model": "llama3:latest"},
        "ModelMgmt",
        "Check if llama3 fits in RAM",
    ),
    (
        "optimac_model_chat",
        {"model": "llama3:latest", "message": "Say 'MCP test passed' in 5 words"},
        "ModelMgmt",
        "Quick chat with loaded model",
    ),
    # ── MODEL TASKS ──
    (
        "optimac_model_task",
        {"task": "What is 2+2?", "model": "llama3:latest"},
        "ModelTask",
        "Simple computation task",
    ),
    (
        "optimac_model_summarize",
        {
            "text": "Quantum computing uses qubits that can be in superposition of 0 and 1 simultaneously, enabling parallel computation. This differs from classical bits which must be either 0 or 1. Quantum entanglement allows qubits to be correlated, providing exponential speedup for certain algorithms like Shor's factoring and Grover's search.",
            "model": "llama3:latest",
        },
        "ModelTask",
        "Summarize text",
    ),
    (
        "optimac_model_route",
        {"task": "What is 2+2?", "prefer": "local"},
        "ModelTask",
        "Route a task to best model",
    ),
    # ── EDGE TOOLS ──
    ("optimac_edge_list", {}, "Edge", "List registered edge nodes"),
    # ── AUTONOMY ──
    ("optimac_watchdog_status", {}, "Autonomy", "Watchdog status — re-check"),
]

# Skip these — too destructive or need specific context:
# optimac_kill_process - kills a process
# optimac_disable_service / enable_service - modifies launchctl
# optimac_disable_spotlight - disables spotlight indexing
# optimac_set_power / power_optimize / power_profile - changes pmset
# optimac_debloat / debloat_reenable - manages services
# optimac_rebuild_spotlight - sudo mdutil
# optimac_clear_caches - needs sudo
# optimac_maintenance_cycle - touches network + sudo
# optimac_sys_lock - locks screen
# optimac_sys_restart_service - restarts a service
# optimac_ollama_start / stop - lifecycle management
# optimac_mlx_serve / stop - lifecycle management
# optimac_swap_model - unloads/loads models
# optimac_model_serve / unload - model lifecycle
# optimac_model_dir_set - changes directory
# optimac_model_code_review - needs file content
# optimac_model_generate - generates code (long)
# optimac_model_edit - needs file + instruction
# optimac_model_commit - needs git context
# optimac_cloud_escalate / edge_escalate - need API keys
# optimac_edge_add / edge_remove / edge_test - modify edge config
# optimac_mlx_quantize - downloads + converts model
# optimac_model_benchmark - already tested


async def main():
    script = str(
        Path(__file__).parent.parent / "optimac-mcp-server" / "dist" / "index.js"
    )
    client = MCPClient(
        {"name": "optimac", "type": "stdio", "command": "node", "args": [script]}
    )

    print("Connecting to MCP server...")
    if not await client.connect():
        print("ERROR: Could not connect")
        return

    tools = await client.list_tools()
    tool_names = {t["name"] for t in tools}
    print(f"Connected. {len(tools)} tools registered.\n")

    baseline = mem()
    print(f"{'=' * 80}")
    print(f"  BASELINE: {baseline[0]}MB used / {baseline[1]}MB ({baseline[2]}%)")
    print(f"  Testing {len(TOOLS)} remaining tools (non-network, non-destructive)")
    print(f"{'=' * 80}\n")

    results = []
    passed = 0
    failed = 0
    skipped = 0

    for i, (name, args, cat, notes) in enumerate(TOOLS):
        label = f"[{i + 1:2d}/{len(TOOLS)}]"

        if name not in tool_names:
            print(f"{label} ⏭ {name} — NOT REGISTERED (skipped)")
            skipped += 1
            results.append((name, cat, "SKIP", 0, "Not registered"))
            continue

        before = mem()
        start = time.time()

        try:
            result = await asyncio.wait_for(
                client.execute_tool(name, args), timeout=60.0
            )
            dur = round(time.time() - start, 2)
            is_err = result.get("isError", False)
            output = ""
            for c in result.get("content", []):
                if c.get("type") == "text":
                    output += c.get("text", "")

            after = mem()

            if is_err:
                # Some errors are expected (like ejecting non-existent volume)
                expected_error = (
                    "nonexistent" in str(args)
                    or "test_trash" in str(args)
                    or "test_nonexistent" in str(args)
                )
                if expected_error:
                    icon = "⚠️"
                    status = "EXPECTED_ERR"
                    passed += 1
                else:
                    icon = "❌"
                    status = "FAIL"
                    failed += 1
            else:
                icon = "✅"
                status = "PASS"
                passed += 1

            preview = output[:120].replace("\n", " ").strip()
            mem_delta = after[0] - before[0]
            sign = f"+{mem_delta}" if mem_delta > 0 else str(mem_delta)

            print(f"{label} {icon} {name} ({dur}s) [{cat}] mem:{sign}MB")
            print(f"       {notes}")
            print(f"       → {preview}...")
            print()

            results.append((name, cat, status, dur, preview))

        except asyncio.TimeoutError:
            dur = round(time.time() - start, 2)
            print(f"{label} ⏰ {name} TIMEOUT ({dur}s) [{cat}]")
            print(f"       {notes}")
            print()
            failed += 1
            results.append((name, cat, "TIMEOUT", dur, "Timed out after 60s"))

        except Exception as e:
            dur = round(time.time() - start, 2)
            print(f"{label} 💥 {name} ERROR ({dur}s): {e}")
            print()
            failed += 1
            results.append((name, cat, "ERROR", dur, str(e)[:120]))

    # Final summary
    final = mem()
    print(f"{'=' * 80}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"  Memory: {baseline[0]}MB → {final[0]}MB (Δ{final[0] - baseline[0]:+d}MB)")
    print(f"{'=' * 80}")

    # Write markdown results
    md = [
        "# Remaining MCP Tools — Manual Test Results",
        f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Result:** {passed} passed, {failed} failed, {skipped} skipped\n",
        "| # | Tool | Category | Status | Time | Output |",
        "|---|------|----------|--------|------|--------|",
    ]
    for j, (n, c, s, d, p) in enumerate(results):
        icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "SKIP": "⏭",
            "TIMEOUT": "⏰",
            "ERROR": "💥",
            "EXPECTED_ERR": "⚠️",
        }.get(s, "?")
        md.append(f"| {j + 1} | `{n}` | {c} | {icon} {s} | {d}s | {p[:60]}... |")

    md.append(
        f"\n**Memory:** {baseline[0]}MB → {final[0]}MB (Δ{final[0] - baseline[0]:+d}MB)"
    )

    Path(__file__).parent.joinpath("remaining_tools_results.md").write_text(
        "\n".join(md)
    )
    print(f"\nResults written to tests/remaining_tools_results.md")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
