# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GerdsenAI OptiMac** is a macOS menu bar app + MCP server for Apple Silicon optimization and AI inference management. The project has two main components:
- **GUI (Python)**: Menu bar app built with `rumps`, system monitoring via `psutil`, native macOS integration with `pyobjc`
- **MCP Server (TypeScript)**: Node.js server with 60+ tools for system control, AI stack management (Ollama, LM Studio, MLX), and three-tier inference routing (local/edge/cloud)

Repository branches: `main` (stable) and `expand` (active development).

## Quick Start Commands

### Python GUI Setup
```bash
# Initial setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the GUI in development
python3 gerdsenai_optimac/gui/menu_app.py

# Build as standalone .app + .dmg
bash scripts/build.sh

# Install built app
open GerdsenAI_OptiMac_*.dmg  # then drag app to Applications
```

### MCP Server Setup
```bash
cd optimac-mcp-server

# Install dependencies
npm install

# Development
npm run dev          # Watch TypeScript, auto-rebuild

# Build and run
npm run build        # Compile to dist/index.js
npm start            # Run the server

# Testing
npm test             # Run full test suite
npm run test:watch   # Watch mode
```

## Architecture

### Python GUI Layer
**Root**: `gerdsenai_optimac/`
- `gui/menu_app.py`: Main entry point, menu bar UI, status monitoring loop
- `gui/handlers/`: Command execution organized by category:
  - `system/`: Process kill, service control, DNS, network
  - `performance/`: Power settings, cache clearing, UI reduction
  - `ai_stack/`: Ollama/MLX/LM Studio lifecycle
  - `optimize/`: Debloat, NVRAM tuning, comprehensive optimization
  - `security/`: Firewall, privacy, system hardening
  - `network/`: DNS presets, connectivity diagnostics
- `gui/dialogs.py`: Modal windows (confirmation, text input, password)
- `gui/monitors.py`: Real-time memory, CPU, thermal monitoring
- `gui/terminal_widget.py`: Embedded terminal for command output
- `gui/icons.py`: Icon generation and dark/light mode support
- `gui/themes.py`: Color constants
- `gui/commands.py`: Helper functions for MCP calls and shell commands
- `gui/sudo.py`: Passwordless sudo prompt handling
- `mcp/`: MCP client integration (client.py, discovery.py, registry.py)

**Key Pattern**: Handlers execute MCP tools when available, fallback to shell commands. All long-running operations spawn async tasks. State is shared via the main `menu_app.py` App instance.

### TypeScript MCP Server
**Root**: `optimac-mcp-server/src/`
- `index.ts`: Server initialization, tool registration
- `services/`:
  - `inference.ts`: Local model inference (Ollama, MLX, LM Studio)
  - `inference-edge.ts`: LAN/network endpoint routing
  - `system.ts`: System monitoring and control (memory, processes, thermal)
  - `power.ts`: Power settings (pmset)
  - `network.ts`: DNS, routing, connectivity
  - `config.ts`: Configuration file management
- `tools/`: MCP tool implementations, organized by category (system-monitoring, system-control, ai-stack, models, tasks, etc.)

**Key Pattern**: All system commands use shell execution with safety checks. Model operations enforce 20% RAM headroom. Three-tier routing tries local → edge → cloud. Config lives in `~/.optimac/config.json`.

### Build & Distribution
- `scripts/build.sh`: PyInstaller .app bundle + DMG creation (drag-to-Applications UI)
- `pyproject.toml`: Python package metadata, entry point at `gerdsenai_optimac.gui.menu_app:main`
- `requirements.txt`: Core dependencies (psutil, rumps, Pillow, pyobjc, mcp, aiohttp)

## Development Workflow

### Adding a GUI Command
1. Add handler method in appropriate `gui/handlers/<category>.py` file
2. Handler calls `self.app.mcp_client.call_tool(tool_name, params)` if available
3. Update menu structure in `gui/menu_app.py` to expose the command
4. Test in dev mode: `python3 gerdsenai_optimac/gui/menu_app.py`

### Adding an MCP Tool
1. Create tool function in `optimac-mcp-server/src/tools/<category>.ts`
2. Register in `src/index.ts` tool registry
3. Implement using services from `src/services/`
4. Use `zod` for parameter validation
5. Test: `npm run test` or `npm run test:watch`
6. Rebuild: `npm run build`

### Important Patterns

**MCP Tool Structure**:
```typescript
{
  name: "optimac_example",
  description: "Brief description",
  inputSchema: z.object({ /* Zod schema */ }),
  execute: async (input) => { /* Return { content: [...] } */ }
}
```

**GUI Handler Pattern**:
```python
async def example_action(self):
    try:
        result = await self.app.mcp_client.call_tool("optimac_example", {})
        self.app.show_notification(result.get("summary", "Done"))
    except Exception as e:
        self.app.show_error(f"Failed: {e}")
```

**Config Access** (MCP):
- Read: `const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'))`
- Write: Use `config.ts` utilities for atomic saves
- Location: `~/.optimac/config.json` (created on first run)

**RAM Safety**: Model tools check available RAM against 20% headroom policy. Use `optimac_model_ram_check` before loading large models.

## Common Tasks

### Build for Release
```bash
bash scripts/build.sh  # Creates dist/GerdsenAI OptiMac.app + .dmg
```

### Run MCP Server Standalone
```bash
cd optimac-mcp-server
npm run build
node dist/index.js
```

### Test a Single MCP Tool
```bash
cd optimac-mcp-server
npm run test -- src/tools/example.ts  # if using Vitest
```

### Debug GUI Issues
Enable verbose logging by modifying `gui/menu_app.py` to print MCP responses. Check terminal output when running from command line.

### Reset Configuration
```bash
rm ~/.optimac/config.json
# App will recreate with defaults on next launch
```

## Key Dependencies

**Python**: psutil (system stats), rumps (menu bar), pyobjc-framework-Cocoa (native UI), Pillow (icon generation), mcp (client), aiohttp (async HTTP)

**TypeScript/Node**: @modelcontextprotocol/sdk (MCP), zod (validation), tsx (dev watch)

## Platform Requirements
- macOS 14+ (Sonoma or later)
- Node.js 18+ (for MCP server)
- Python 3.9+ (for GUI)
- Apple Silicon (M4/M4 Pro) — some optimizations are CPU-specific
- Passwordless sudo (optional but recommended for system commands)

## Testing Notes

**Python**: No formal test framework in use. Test GUI manually or via MCP client calls.

**TypeScript**: Vitest configured. Run `npm test` in `optimac-mcp-server/`. Tests should validate tool parameter schemas and edge cases (RAM checks, missing services, etc.).

## Debugging

- **GUI hangs**: Check if a long-running MCP call is blocking. Ensure handlers spawn async tasks.
- **MCP tool errors**: Check stderr in terminal where server is running. Use `zod.parse()` to validate inputs.
- **Config issues**: Verify `~/.optimac/config.json` is valid JSON. Check permissions.
- **System command failures**: Some require `sudo` or disabled SIP. Check tool documentation in `MCP_COMMANDS.md`.
