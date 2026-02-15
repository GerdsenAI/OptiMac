#!/usr/bin/env python3
"""Benchmark llama3 via MCP with GPU + memory monitoring."""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient


def mem_snapshot():
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


async def main():
    script = str(
        Path(__file__).parent.parent / "optimac-mcp-server" / "dist" / "index.js"
    )
    client = MCPClient(
        {"name": "optimac", "type": "stdio", "command": "node", "args": [script]}
    )

    print("Connecting...")
    if not await client.connect():
        print("FAIL")
        return
    print("Connected\n")

    # GPU before (via MCP)
    gpu_b = await client.execute_tool("optimac_gpu_stats", {})
    gpu_b_txt = "".join(c.get("text", "") for c in gpu_b.get("content", []))
    gpu_lines_b = [l.strip() for l in gpu_b_txt.split("\n") if "active" in l.lower()]

    used_b, total_b, pct_b = mem_snapshot()
    print(f"BEFORE: Memory {used_b}MB/{total_b}MB ({pct_b}%)")
    for l in gpu_lines_b[:2]:
        print(f"  {l}")

    # Benchmark
    print(f"\n⏳ Benchmarking llama3:latest...")
    t0 = time.time()

    result = await asyncio.wait_for(
        client.execute_tool(
            "optimac_model_benchmark",
            {
                "model": "llama3:latest",
                "prompt": "Explain quantum computing in exactly 100 words.",
            },
        ),
        timeout=300.0,
    )

    wall = round(time.time() - t0, 2)
    output = "".join(c.get("text", "") for c in result.get("content", []))
    is_err = result.get("isError", False)

    if is_err:
        print(f"\n❌ FAILED ({wall}s): {output[:300]}")
        await client.disconnect()
        return

    # After
    used_a, total_a, pct_a = mem_snapshot()
    gpu_a = await client.execute_tool("optimac_gpu_stats", {})
    gpu_a_txt = "".join(c.get("text", "") for c in gpu_a.get("content", []))
    gpu_lines_a = [l.strip() for l in gpu_a_txt.split("\n") if "active" in l.lower()]

    print(f"\n✅ BENCHMARK COMPLETE ({wall}s wall clock)")
    print(f"\n{output}")

    print(f"\nAFTER:  Memory {used_a}MB/{total_a}MB ({pct_a}%)")
    for l in gpu_lines_a[:2]:
        print(f"  {l}")

    s = lambda v: f"+{v}" if v > 0 else str(v)
    print(
        f"\nDELTA: Mem {s(used_a - used_b)}MB | Pressure {s(round(pct_a - pct_b, 1))}%"
    )

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
