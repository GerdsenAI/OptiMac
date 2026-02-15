#!/usr/bin/env python3
"""Re-run failed tools with corrected arguments + test additional untested tools."""

import asyncio
import subprocess
import sys
import time
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


TOOLS = [
    # ── FIXED: config_set needs enum key + proper value type ──
    (
        "optimac_config_set",
        {"key": "maxProcessRSSMB", "value": 2048},
        "Config",
        "Set maxProcessRSSMB (number)",
    ),
    # ── FIXED: model_ram_check needs size_gb (number), not model name ──
    (
        "optimac_model_ram_check",
        {"size_gb": 4.7, "model_name": "llama3:latest"},
        "ModelMgmt",
        "Can 4.7GB llama3 fit?",
    ),
    # ── FIXED: model_chat uses 'prompt' not 'message' ──
    (
        "optimac_model_chat",
        {"prompt": "Say 'MCP test passed' in 5 words", "runtime": "ollama"},
        "ModelMgmt",
        "Chat via Ollama API",
    ),
    # ── FIXED: model_summarize needs 'paths' array, not 'text' ──
    (
        "optimac_model_summarize",
        {"paths": ["./optimac-mcp-server/src/index.ts"], "format": "brief"},
        "ModelTask",
        "Summarize index.ts",
    ),
    # ── sec_audit_auth: re-test as-is, see if error is consistent ──
    ("optimac_sec_audit_auth", {}, "Security", "Failed logins audit"),
    # ── ADDITIONAL UNTESTED TOOLS ──
    (
        "optimac_config_protect_process",
        {"process_name": "__test_process__"},
        "Config",
        "Add test to protected list",
    ),
    (
        "optimac_config_unprotect_process",
        {"process_name": "__test_process__"},
        "Config",
        "Remove test from protected",
    ),
    # Model tasks with file context
    (
        "optimac_model_code_review",
        {
            "paths": ["./optimac-mcp-server/src/services/shell.ts"],
            "focus": "error handling",
        },
        "ModelTask",
        "Code review shell.ts",
    ),
    # Edge tools
    (
        "optimac_edge_add",
        {"name": "test-node", "url": "http://localhost:9999", "models": ["test-model"]},
        "Edge",
        "Add test edge node",
    ),
    ("optimac_edge_list", {}, "Edge", "List edges (should show test-node)"),
    ("optimac_edge_remove", {"name": "test-node"}, "Edge", "Remove test edge node"),
    ("optimac_edge_list", {}, "Edge", "List edges (should be empty again)"),
]


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

    baseline = mem()
    passed = 0
    failed = 0

    for i, (name, args, cat, notes) in enumerate(TOOLS):
        before = mem()
        start = time.time()

        try:
            result = await asyncio.wait_for(
                client.execute_tool(name, args), timeout=120.0
            )
            dur = round(time.time() - start, 2)
            is_err = result.get("isError", False)
            output = ""
            for c in result.get("content", []):
                if c.get("type") == "text":
                    output += c.get("text", "")

            after = mem()
            icon = "❌" if is_err else "✅"
            if is_err:
                failed += 1
            else:
                passed += 1

            md = after[0] - before[0]
            sign = f"+{md}" if md > 0 else str(md)
            preview = output[:150].replace("\n", " ").strip()

            print(
                f"[{i + 1:2d}/{len(TOOLS)}] {icon} {name} ({dur}s) [{cat}] mem:{sign}MB"
            )
            print(f"       {notes}")
            print(f"       → {preview}")
            print()

        except asyncio.TimeoutError:
            print(f"[{i + 1:2d}/{len(TOOLS)}] ⏰ {name} TIMEOUT [{cat}]")
            print(f"       {notes}\n")
            failed += 1

        except Exception as e:
            print(f"[{i + 1:2d}/{len(TOOLS)}] 💥 {name} ERROR: {e}\n")
            failed += 1

    final = mem()
    print(f"{'=' * 70}")
    print(f"  {passed} passed, {failed} failed")
    print(f"  Memory: {baseline[0]}MB → {final[0]}MB (Δ{final[0] - baseline[0]:+d}MB)")
    print(f"{'=' * 70}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
