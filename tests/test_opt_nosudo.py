#!/usr/bin/env python3
"""Quick test for non-sudo optimization tools with before/after monitoring."""

import asyncio
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient


def snapshot():
    """Quick memory + disk snapshot."""
    # Memory
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
    total = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
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

    free = stats.get("Pages free", 0) / (1024**2)
    active = stats.get("Pages active", 0) / (1024**2)
    wired = stats.get("Pages wired down", 0) / (1024**2)
    compressed = stats.get("Pages occupied by compressor", 0) / (1024**2)
    inactive = stats.get("Pages inactive", 0) / (1024**2)
    purgeable = stats.get("Pages purgeable", 0) / (1024**2)
    used = active + wired + compressed
    total_mb = total / (1024**2)

    # Disk
    df = subprocess.run(
        ["df", "-m", "/"], capture_output=True, text=True, timeout=5
    ).stdout
    parts = df.split("\n")[1].split()

    return {
        "mem_used": round(used),
        "mem_free": round(free),
        "mem_inactive": round(inactive),
        "mem_purgeable": round(purgeable),
        "mem_total": round(total_mb),
        "pressure": round(used / total_mb * 100, 1),
        "disk_used": int(parts[2]),
        "disk_avail": int(parts[3]),
    }


TOOLS = [
    {
        "name": "optimac_reduce_ui_overhead",
        "args": {},
        "label": "Reduce UI Overhead",
        "desc": "Disable animations, transparency, smooth scrolling — frees GPU resources",
    },
    {
        "name": "optimac_optimize_homebrew",
        "args": {},
        "label": "Optimize Homebrew",
        "desc": "brew cleanup --prune=7 && brew autoremove",
    },
]


async def main():
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

    print("Connecting...")
    if not await client.connect():
        print("ERROR")
        return
    print("Connected\n")

    for i, tool in enumerate(TOOLS):
        before = snapshot()
        print(f"── {tool['label']} ──")
        print(f"  {tool['desc']}")
        print(
            f"  BEFORE: Mem {before['mem_used']}MB used ({before['pressure']}%) | Free {before['mem_free']}MB | Disk {before['disk_avail']}MB avail"
        )

        start = time.time()
        try:
            result = await asyncio.wait_for(
                client.execute_tool(tool["name"], tool["args"]), timeout=120.0
            )
            dur = round(time.time() - start, 2)
            is_err = result.get("isError", False)
            output = ""
            for c in result.get("content", []):
                if c.get("type") == "text":
                    output += c.get("text", "")

            await asyncio.sleep(1)  # let system settle
            after = snapshot()

            icon = "❌" if is_err else "✅"
            print(f"  {icon} ({dur}s)")
            print(
                f"  AFTER:  Mem {after['mem_used']}MB used ({after['pressure']}%) | Free {after['mem_free']}MB | Disk {after['disk_avail']}MB avail"
            )

            s = lambda v: f"+{v}" if v > 0 else str(v)
            print(
                f"  DELTA:  Mem Used {s(after['mem_used']-before['mem_used'])}MB | Free {s(after['mem_free']-before['mem_free'])}MB | Pressure {s(round(after['pressure']-before['pressure'],1))}%"
            )
            print(
                f"          Disk Used {s(after['disk_used']-before['disk_used'])}MB | Avail {s(after['disk_avail']-before['disk_avail'])}MB"
            )

            # Show output preview
            preview = output[:300].replace("\n", "\n  ")
            print(f"  OUTPUT:\n  {preview}")
            if is_err:
                print(f"  ⚠️ Tool returned error flag")
        except Exception as e:
            print(f"  ❌ {e}")
        print()

    await client.disconnect()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
