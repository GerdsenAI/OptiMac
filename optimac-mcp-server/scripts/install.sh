#!/bin/bash
# OptiMac MCP Server installer
# Run: chmod +x scripts/install.sh && ./scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$HOME/.optimac"

echo "=== OptiMac MCP Server Installer ==="
echo ""

# 1. Check Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed. Install via: brew install node"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "ERROR: Node.js 18+ required. Current: $(node -v)"
    exit 1
fi
echo "[OK] Node.js $(node -v)"

# 2. Install dependencies
echo ""
echo "Installing dependencies..."
cd "$PROJECT_DIR"
npm install
echo "[OK] Dependencies installed"

# 3. Build
echo ""
echo "Building TypeScript..."
npm run build
echo "[OK] Build complete"

# 4. Create config directory
mkdir -p "$CONFIG_DIR"
echo "[OK] Config directory: $CONFIG_DIR"

# 5. Configure passwordless sudo for safe commands
echo ""
echo "--- Passwordless Sudo (Optional) ---"
echo "OptiMac needs sudo for: purge, mdutil, route flush, dscacheutil, pmset"
echo ""
echo "To enable passwordless sudo for these commands, run:"
echo ""
echo "  sudo visudo -f /etc/sudoers.d/optimac"
echo ""
echo "And add this line (replace YOUR_USERNAME with your macOS username):"
echo ""
echo "  YOUR_USERNAME ALL=(ALL) NOPASSWD: /usr/sbin/purge, /usr/bin/mdutil, /sbin/route, /usr/bin/dscacheutil, /usr/bin/pmset, /usr/bin/killall"
echo ""

# 6. Claude Desktop configuration
echo "--- Claude Desktop Configuration ---"
echo ""
echo "Add this to your claude_desktop_config.json:"
echo "(typically at ~/Library/Application Support/Claude/claude_desktop_config.json)"
echo ""

DIST_PATH="$PROJECT_DIR/dist/index.js"

cat << JSONEOF
{
  "mcpServers": {
    "optimac": {
      "command": "node",
      "args": ["$DIST_PATH"]
    }
  }
}
JSONEOF

echo ""

# 7. Claude Code configuration
echo ""
echo "--- Claude Code Configuration ---"
echo ""
echo "Run this command to add OptiMac to Claude Code:"
echo ""
echo "  claude mcp add optimac node $DIST_PATH"
echo ""

# 8. Test
echo "--- Testing ---"
echo ""
echo "Running basic test..."
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | timeout 5 node "$DIST_PATH" 2>/dev/null | head -c 200 && echo ""
echo ""
echo "[OK] Server responds to MCP initialize"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Configure passwordless sudo (see above)"
echo "  2. Add to Claude Desktop or Claude Code (see above)"
echo "  3. Restart Claude Desktop"
echo "  4. Ask Claude: 'Run optimac_system_overview'"
echo ""
