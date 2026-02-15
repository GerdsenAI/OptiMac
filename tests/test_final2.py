#!/usr/bin/env python3
"""Final re-test of the last 2 failing tools."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from gerdsenai_optimac.mcp.client import MCPClient


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

    tools = [
        ("optimac_sec_audit_auth", {}, "Failed logins audit (fixed shell: true)"),
        (
            "optimac_model_code_review",
            {
                "repo_path": "/Users/gerdsenai/Documents/OptiMac",
                "target": "uncommitted",
                "focus": "error handling",
            },
            "Code review uncommitted changes",
        ),
    ]

    for name, args, desc in tools:
        print(f"── {name} ──")
        print(f"   {desc}")
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

            icon = "❌" if is_err else "✅"
            print(f"   {icon} ({dur}s)")
            preview = output[:300].replace("\n", "\n   ")
            print(f"   {preview}")

        except asyncio.TimeoutError:
            print(f"   ⏰ TIMEOUT")
        except Exception as e:
            print(f"   💥 {e}")
        print()

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
