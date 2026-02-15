#!/usr/bin/env python3
"""
Manual optimization test — runs 4 optimization MCP tools with detailed
before/after system monitoring (memory, disk, GPU).

Tools tested:
  1. optimac_purge_memory     — frees inactive memory pages
  2. optimac_clear_caches     — clears /tmp, ~/Library/Caches, old logs
  3. optimac_reduce_ui_overhead — disables macOS animations/transparency
  4. optimac_optimize_homebrew — brew cleanup + autoremove
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient


def run(cmd, args=None):
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(
            [cmd] + (args or []), capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def snapshot_memory():
    """Get memory stats in MB."""
    vm = run("vm_stat")
    total = int(run("sysctl", ["-n", "hw.memsize"]))
    page = 16384  # Apple Silicon

    stats = {}
    for line in vm.split("\n")[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip().rstrip(".")
            if v.isdigit():
                stats[k.strip()] = int(v) * page

    free_mb = stats.get("Pages free", 0) / (1024**2)
    active_mb = stats.get("Pages active", 0) / (1024**2)
    inactive_mb = stats.get("Pages inactive", 0) / (1024**2)
    purgeable_mb = stats.get("Pages purgeable", 0) / (1024**2)
    wired_mb = stats.get("Pages wired down", 0) / (1024**2)
    compressed_mb = stats.get("Pages occupied by compressor", 0) / (1024**2)
    speculative_mb = stats.get("Pages speculative", 0) / (1024**2)
    total_mb = total / (1024**2)
    used_mb = active_mb + wired_mb + compressed_mb

    return {
        "total_mb": round(total_mb),
        "used_mb": round(used_mb),
        "free_mb": round(free_mb),
        "inactive_mb": round(inactive_mb),
        "purgeable_mb": round(purgeable_mb),
        "compressed_mb": round(compressed_mb),
        "wired_mb": round(wired_mb),
        "speculative_mb": round(speculative_mb),
        "pressure_pct": round(used_mb / total_mb * 100, 1),
    }


def snapshot_disk():
    """Get root disk usage."""
    df = run("df", ["-m", "/"])
    lines = df.split("\n")
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 4:
            return {
                "total_mb": int(parts[1]),
                "used_mb": int(parts[2]),
                "avail_mb": int(parts[3]),
            }
    return {"error": "could not parse df"}


def snapshot_gpu():
    """Get GPU utilization."""
    try:
        gpu = subprocess.run(
            ["sudo", "powermetrics", "--samplers", "gpu_power", "-n", "1", "-i", "500"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = gpu.stdout.split("\n")
        active_line = [l for l in lines if "active residency" in l.lower()]
        freq_line = [l for l in lines if "active frequency" in l.lower()]
        return {
            "frequency": freq_line[0].strip() if freq_line else "N/A",
            "residency": active_line[0].strip() if active_line else "N/A",
        }
    except Exception:
        # Fallback: use the MCP gpu_stats tool output for this
        return {"info": "captured via MCP tool"}


def snapshot_all():
    """Combined system snapshot."""
    return {
        "memory": snapshot_memory(),
        "disk": snapshot_disk(),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


def fmt_delta_mem(before, after):
    """Format memory deltas."""
    sign = lambda v: f"+{v}" if v > 0 else str(v)
    return (
        f"Δ Used: {sign(after['used_mb'] - before['used_mb'])}MB | "
        f"Δ Free: {sign(after['free_mb'] - before['free_mb'])}MB | "
        f"Δ Inactive: {sign(after['inactive_mb'] - before['inactive_mb'])}MB | "
        f"Δ Purgeable: {sign(after['purgeable_mb'] - before['purgeable_mb'])}MB | "
        f"Δ Pressure: {sign(round(after['pressure_pct'] - before['pressure_pct'], 1))}%"
    )


def fmt_delta_disk(before, after):
    """Format disk deltas."""
    if "error" in before or "error" in after:
        return "disk snapshot error"
    sign = lambda v: f"+{v}" if v > 0 else str(v)
    return (
        f"Δ Used: {sign(after['used_mb'] - before['used_mb'])}MB | "
        f"Δ Available: {sign(after['avail_mb'] - before['avail_mb'])}MB"
    )


OPTIMIZATION_TOOLS = [
    {
        "name": "optimac_purge_memory",
        "args": {},
        "label": "Purge Memory",
        "desc": "sudo purge — reclaims inactive/purgeable memory pages",
        "metric": "memory",  # what to focus on
    },
    {
        "name": "optimac_clear_caches",
        "args": {},
        "label": "Clear Caches",
        "desc": "Clear /tmp, ~/Library/Caches, old logs >7 days",
        "metric": "disk",
    },
    {
        "name": "optimac_reduce_ui_overhead",
        "args": {},
        "label": "Reduce UI Overhead",
        "desc": "Disable animations, transparency, smooth scrolling — frees GPU resources",
        "metric": "memory",  # slight GPU VRAM impact
    },
    {
        "name": "optimac_optimize_homebrew",
        "args": {},
        "label": "Optimize Homebrew",
        "desc": "brew cleanup --prune=7 && brew autoremove",
        "metric": "disk",
    },
]


async def main():
    # Connect
    server_script = str(
        Path(__file__).parent.parent / "optimac-mcp-server" / "dist" / "index.js"
    )
    client = MCPClient(
        {
            "name": "optimac",
            "type": "stdio",
            "command": "node",
            "args": [server_script],
        }
    )

    print("Connecting to MCP server...")
    if not await client.connect():
        print("ERROR: Could not connect")
        return

    tools = await client.list_tools()
    tool_names = {t["name"] for t in tools}
    print(f"Connected ({len(tools)} tools)\n")

    # Global baseline
    baseline = snapshot_all()
    print(f"{'='*80}")
    print(f"  SYSTEM BASELINE ({baseline['timestamp']})")
    print(f"{'='*80}")
    m = baseline["memory"]
    d = baseline["disk"]
    print(
        f"  Memory: {m['used_mb']}MB used / {m['total_mb']}MB ({m['pressure_pct']}% pressure)"
    )
    print(
        f"          Free: {m['free_mb']}MB | Inactive: {m['inactive_mb']}MB | Purgeable: {m['purgeable_mb']}MB"
    )
    print(
        f"  Disk:   {d['used_mb']}MB used / {d['total_mb']}MB ({d['avail_mb']}MB available)"
    )
    print()

    # Results
    md_lines = []
    md_lines.append("# Optimization MCP Tools — Live Test Results")
    md_lines.append(f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"\n## System Baseline")
    md_lines.append(f"| Metric | Value |")
    md_lines.append(f"|--------|-------|")
    md_lines.append(
        f"| Memory Used | {m['used_mb']}MB / {m['total_mb']}MB ({m['pressure_pct']}%) |"
    )
    md_lines.append(f"| Memory Free | {m['free_mb']}MB |")
    md_lines.append(f"| Memory Inactive | {m['inactive_mb']}MB |")
    md_lines.append(f"| Memory Purgeable | {m['purgeable_mb']}MB |")
    md_lines.append(f"| Disk Used | {d['used_mb']}MB / {d['total_mb']}MB |")
    md_lines.append(f"| Disk Available | {d['avail_mb']}MB |")
    md_lines.append("")

    all_passed = True

    for i, tool in enumerate(OPTIMIZATION_TOOLS):
        name = tool["name"]
        label = tool["label"]
        desc = tool["desc"]
        metric = tool["metric"]

        print(f"{'─'*80}")
        print(f"  [{i+1}/4] {label}")
        print(f"  {desc}")
        print(f"{'─'*80}")

        if name not in tool_names:
            print(f"  ⏭ SKIPPED — not registered\n")
            continue

        # Before
        before = snapshot_all()
        bm = before["memory"]
        bd = before["disk"]
        print(
            f"  BEFORE: Memory {bm['used_mb']}MB used ({bm['pressure_pct']}% pressure) "
            f"| Free {bm['free_mb']}MB | Purgeable {bm['purgeable_mb']}MB"
        )
        print(f"          Disk {bd['used_mb']}MB used | {bd['avail_mb']}MB available")

        # Execute
        print(f"  ⏳ Executing...", end="", flush=True)
        start = time.time()

        try:
            result = await asyncio.wait_for(
                client.execute_tool(name, tool["args"]), timeout=60.0
            )
            duration = round(time.time() - start, 2)

            is_error = result.get("isError", False)
            content = result.get("content", [])
            output = ""
            for c in content:
                if c.get("type") == "text":
                    output += c.get("text", "")

            # Small delay for system to settle
            await asyncio.sleep(0.5)

            # After
            after = snapshot_all()
            am = after["memory"]
            ad = after["disk"]

            status = "❌ FAIL" if is_error else "✅ PASS"
            print(f"\r  {status} ({duration}s)")
            print(
                f"  AFTER:  Memory {am['used_mb']}MB used ({am['pressure_pct']}% pressure) "
                f"| Free {am['free_mb']}MB | Purgeable {am['purgeable_mb']}MB"
            )
            print(
                f"          Disk {ad['used_mb']}MB used | {ad['avail_mb']}MB available"
            )

            mem_delta = fmt_delta_mem(bm, am)
            disk_delta = fmt_delta_disk(bd, ad)
            print(f"  DELTA:  {mem_delta}")
            print(f"          {disk_delta}")

            if is_error:
                all_passed = False
                err_preview = output[:200]
                print(f"  ERROR:  {err_preview}")

            # Truncate output for display
            out_preview = output[:300] if not is_error else output[:500]
            print(f"  OUTPUT: {out_preview[:150]}...")
            print()

            # Write to markdown
            md_lines.append(
                f"## {i+1}. {label} — {'PASS ✅' if not is_error else 'FAIL ❌'}"
            )
            md_lines.append(f"**Tool:** `{name}` | **Duration:** {duration}s")
            md_lines.append(f"\n**Description:** {desc}")
            md_lines.append(f"\n### Before/After")
            md_lines.append(f"| Metric | Before | After | Delta |")
            md_lines.append(f"|--------|--------|-------|-------|")
            md_lines.append(
                f"| Memory Used | {bm['used_mb']}MB | {am['used_mb']}MB | **{am['used_mb']-bm['used_mb']:+d}MB** |"
            )
            md_lines.append(
                f"| Memory Free | {bm['free_mb']}MB | {am['free_mb']}MB | **{am['free_mb']-bm['free_mb']:+d}MB** |"
            )
            md_lines.append(
                f"| Memory Inactive | {bm['inactive_mb']}MB | {am['inactive_mb']}MB | **{am['inactive_mb']-bm['inactive_mb']:+d}MB** |"
            )
            md_lines.append(
                f"| Memory Purgeable | {bm['purgeable_mb']}MB | {am['purgeable_mb']}MB | **{am['purgeable_mb']-bm['purgeable_mb']:+d}MB** |"
            )
            md_lines.append(
                f"| Pressure | {bm['pressure_pct']}% | {am['pressure_pct']}% | **{am['pressure_pct']-bm['pressure_pct']:+.1f}%** |"
            )
            md_lines.append(
                f"| Disk Used | {bd['used_mb']}MB | {ad['used_mb']}MB | **{ad['used_mb']-bd['used_mb']:+d}MB** |"
            )
            md_lines.append(
                f"| Disk Available | {bd['avail_mb']}MB | {ad['avail_mb']}MB | **{ad['avail_mb']-bd['avail_mb']:+d}MB** |"
            )

            md_lines.append(f"\n<details><summary>Tool Output</summary>\n")
            md_lines.append(f"```json\n{output[:2000]}\n```")
            md_lines.append(f"</details>\n")

        except asyncio.TimeoutError:
            print(f"\r  ⏰ TIMEOUT (60s)")
            all_passed = False
            md_lines.append(f"## {i+1}. {label} — TIMEOUT ⏰\n")

        except Exception as e:
            print(f"\r  ❌ ERROR: {e}")
            all_passed = False
            md_lines.append(f"## {i+1}. {label} — ERROR: {e}\n")

    # Final system state
    final = snapshot_all()
    fm = final["memory"]
    fd = final["disk"]
    bm_base = baseline["memory"]
    bd_base = baseline["disk"]

    print(f"{'='*80}")
    print(f"  FINAL SYSTEM STATE ({final['timestamp']})")
    print(f"{'='*80}")
    print(
        f"  Memory: {fm['used_mb']}MB used / {fm['total_mb']}MB ({fm['pressure_pct']}% pressure)"
    )
    print(
        f"          Free: {fm['free_mb']}MB | Inactive: {fm['inactive_mb']}MB | Purgeable: {fm['purgeable_mb']}MB"
    )
    print(
        f"  Disk:   {fd['used_mb']}MB used / {fd['total_mb']}MB ({fd['avail_mb']}MB available)"
    )
    print()
    total_mem_delta = fmt_delta_mem(bm_base, fm)
    total_disk_delta = fmt_delta_disk(bd_base, fd)
    print(f"  OVERALL DELTA (baseline → final):")
    print(f"    {total_mem_delta}")
    print(f"    {total_disk_delta}")
    print()

    # Write final summary
    md_lines.append(f"## Overall Impact (Baseline → Final)")
    md_lines.append(f"| Metric | Baseline | Final | Net Delta |")
    md_lines.append(f"|--------|----------|-------|-----------|")
    md_lines.append(
        f"| Memory Used | {bm_base['used_mb']}MB | {fm['used_mb']}MB | **{fm['used_mb']-bm_base['used_mb']:+d}MB** |"
    )
    md_lines.append(
        f"| Memory Free | {bm_base['free_mb']}MB | {fm['free_mb']}MB | **{fm['free_mb']-bm_base['free_mb']:+d}MB** |"
    )
    md_lines.append(
        f"| Memory Pressure | {bm_base['pressure_pct']}% | {fm['pressure_pct']}% | **{fm['pressure_pct']-bm_base['pressure_pct']:+.1f}%** |"
    )
    md_lines.append(
        f"| Disk Used | {bd_base['used_mb']}MB | {fd['used_mb']}MB | **{fd['used_mb']-bd_base['used_mb']:+d}MB** |"
    )
    md_lines.append(
        f"| Disk Available | {bd_base['avail_mb']}MB | {fd['avail_mb']}MB | **{fd['avail_mb']-bd_base['avail_mb']:+d}MB** |"
    )
    md_lines.append("")

    await client.disconnect()

    # Write results
    results_path = Path(__file__).parent / "optimization_test_results.md"
    results_path.write_text("\n".join(md_lines))
    print(f"Results written to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
