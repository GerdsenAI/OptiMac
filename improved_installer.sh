#!/bin/bash
# GerdsenAI OptiMac v2.0 - Enhanced Installer
# Improved installer with better error handling and requirements management

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print retro-style header
clear
echo -e "${GREEN}"
cat << 'EOF'
 ██████╗ ███████╗██████╗ ██████╗ ███████╗███████╗███╗   ██╗ █████╗ ██╗    
██╔════╝ ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝████╗  ██║██╔══██╗██║    
██║  ███╗█████╗  ██████╔╝██║  ██║███████╗█████╗  ██╔██╗ ██║███████║██║    
██║   ██║██╔══╝  ██╔══██╗██║  ██║╚════██║██╔══╝  ██║╚██╗██║██╔══██║██║    
╚██████╔╝███████╗██║  ██║██████╔╝███████║███████╗██║ ╚████║██║  ██║██║    
 ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝    
                                                                           
                O P T I M A C   v 2 . 0   I N S T A L L E R              
EOF
echo -e "${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This installer is for macOS only"
    exit 1
fi

# Check for Apple Silicon
ARCH=$(uname -m)
if [[ "$ARCH" != "arm64" ]]; then
    print_warning "This tool is optimized for Apple Silicon Macs"
    print_warning "Detected architecture: $ARCH"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if required files exist
print_status "Checking required files..."
REQUIRED_FILES=("gerdsenai_optimac_improved.py" "requirements.txt")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "$file not found in current directory"
        exit 1
    fi
done
print_success "All required files found"

# Check for Python 3
print_status "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not found"
    print_error "Install Python 3 with: brew install python3"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_VERSION_NUM=$(python3 -c 'import sys; print(sys.version_info.major * 10 + sys.version_info.minor)')

if [ "$PYTHON_VERSION_NUM" -lt 38 ]; then
    print_error "Python 3.8+ required (found Python $PYTHON_VERSION)"
    exit 1
fi
print_success "Python $PYTHON_VERSION found"

# Check for tkinter
print_status "Checking tkinter availability..."
if ! python3 -c "import tkinter" 2>/dev/null; then
    print_error "tkinter not available"
    print_error "On macOS, this usually means Python was not installed with tkinter support"
    print_error "Try installing Python via Homebrew: brew install python-tk"
    exit 1
fi
print_success "tkinter available"

# Installation directory
INSTALL_DIR="$HOME/Applications/GerdsenAI OptiMac v2"
print_status "Installation directory: $INSTALL_DIR"

# Create installation directory
print_status "Creating installation directories..."
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/logs"

# Copy application files
print_status "Installing application files..."
cp gerdsenai_optimac_improved.py "$INSTALL_DIR/bin/"
cp requirements.txt "$INSTALL_DIR/"

# Create virtual environment
print_status "Creating virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"

# Activate virtual environment and install requirements
print_status "Installing Python dependencies..."
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"

if [ $? -ne 0 ]; then
    print_error "Failed to install Python dependencies"
    exit 1
fi
print_success "Dependencies installed successfully"

# Create launcher scripts
print_status "Creating launcher scripts..."

# Main launcher
cat > "$INSTALL_DIR/GerdsenAI OptiMac v2.command" << 'EOF'
#!/bin/bash
# GerdsenAI OptiMac v2.0 Launcher

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$DIR/venv/bin/activate"

# Check if we need sudo for full functionality
if [ "$EUID" -ne 0 ]; then
    echo "GerdsenAI OptiMac v2.0"
    echo "======================"
    echo ""
    echo "For full hardware monitoring capabilities, administrator privileges are recommended."
    echo "You can run without sudo, but some features will be limited."
    echo ""
    read -p "Run with sudo? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Please enter your password:"
        exec sudo "$0" "$@"
    fi
fi

# Change to bin directory and run
cd "$DIR/bin"
python3 gerdsenai_optimac_improved.py

# Keep terminal open on exit
echo ""
echo "Press any key to exit..."
read -n 1
EOF

chmod +x "$INSTALL_DIR/GerdsenAI OptiMac v2.command"

# Create command-line launcher
print_status "Creating command-line launcher..."
mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/gerdsenai-optimac" << EOF
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
cd "$INSTALL_DIR/bin"
python3 gerdsenai_optimac_improved.py "\$@"
EOF

chmod +x "$HOME/.local/bin/gerdsenai-optimac"

# Create desktop shortcut
if [ -d "$HOME/Desktop" ]; then
    print_status "Creating desktop shortcut..."
    ln -sf "$INSTALL_DIR/GerdsenAI OptiMac v2.command" "$HOME/Desktop/GerdsenAI OptiMac v2"
fi

# Create application info
cat > "$INSTALL_DIR/app_info.txt" << EOF
GerdsenAI OptiMac v2.0 - Terminal Edition
========================================

Installation Date: $(date)
Python Version: $PYTHON_VERSION
Install Location: $INSTALL_DIR

Features:
- Real-time system monitoring for Apple Silicon Macs
- CPU and Memory stress testing
- System optimization commands
- Retro terminal interface
- Network bandwidth monitoring
- Power consumption tracking (requires sudo)

Launch Options:
1. Double-click: GerdsenAI OptiMac v2.command
2. Command line: gerdsenai-optimac
3. Desktop shortcut: GerdsenAI OptiMac v2

System Requirements:
- macOS 10.15+
- Apple Silicon Mac (M1, M2, M3, M4)
- Python 3.8+
- Administrator privileges (optional but recommended)

For support: https://github.com/gerdsenai/optimac
EOF

# Create uninstaller
cat > "$INSTALL_DIR/uninstall.command" << EOF
#!/bin/bash
echo "Uninstalling GerdsenAI OptiMac v2.0..."
rm -rf "$INSTALL_DIR"
rm -f "$HOME/Desktop/GerdsenAI OptiMac v2"
rm -f "$HOME/.local/bin/gerdsenai-optimac"
echo "Uninstalled successfully"
read -p "Press any key to continue..."
EOF
chmod +x "$INSTALL_DIR/uninstall.command"

# Create README
cat > "$INSTALL_DIR/README.md" << 'EOF'
# GerdsenAI OptiMac v2.0

Performance monitoring and optimization tool for Apple Silicon Macs.

## Features

- **Real-time Monitoring**: CPU, memory, power consumption, and network statistics
- **Stress Testing**: CPU and memory stress tests without external dependencies
- **System Optimization**: Automated system optimization commands
- **Retro Interface**: Classic terminal-style GUI with green-on-black theme
- **Cross-Platform**: Supports all Apple Silicon variants (M1, M2, M3, M4)

## Usage

### GUI Mode
```bash
# Launch with GUI
./GerdsenAI\ OptiMac\ v2.command

# Or from command line
gerdsenai-optimac
```

### Sudo Mode (Recommended)
For full hardware monitoring capabilities, run with administrator privileges:
```bash
sudo gerdsenai-optimac
```

## Controls

- **MONITOR**: Start/stop real-time system monitoring
- **CPU TEST**: Run CPU stress test (30 seconds)
- **MEM TEST**: Run memory allocation stress test
- **OPTIMIZE**: Execute system optimization commands
- **CLEAR**: Clear terminal output
- **EXIT**: Quit application

## System Requirements

- macOS 10.15 or later
- Apple Silicon Mac (M1/M2/M3/M4)
- Python 3.8+
- psutil library (installed automatically)

## Troubleshooting

### Limited Features Warning
If you see "NO SUDO - LIMITED FEATURES", run with sudo for full capabilities:
```bash
sudo gerdsenai-optimac
```

### Permission Errors
Ensure the application has necessary permissions in System Preferences > Security & Privacy.

### Python Issues
If you encounter Python-related errors, ensure you have Python 3.8+ installed:
```bash
python3 --version
```

## Uninstallation

Run the uninstaller:
```bash
./uninstall.command
```

Or manually remove:
```bash
rm -rf "$HOME/Applications/GerdsenAI OptiMac v2"
rm -f "$HOME/Desktop/GerdsenAI OptiMac v2"
rm -f "$HOME/.local/bin/gerdsenai-optimac"
```
EOF

# Check PATH for command-line launcher
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    print_warning "Command-line launcher may not be in PATH"
    print_warning "Add this to your shell profile (.zshrc or .bash_profile):"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# Final success message
echo ""
echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}           Installation Complete!${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo ""
echo -e "${CYAN}Installed to:${NC} $INSTALL_DIR"
echo ""
echo -e "${CYAN}Launch Options:${NC}"
echo -e "  Desktop: Double-click 'GerdsenAI OptiMac v2'"
echo -e "  Terminal: ${YELLOW}gerdsenai-optimac${NC}"
echo -e "  Finder: Open '$INSTALL_DIR'"
echo ""
echo -e "${CYAN}For full functionality:${NC} ${YELLOW}sudo gerdsenai-optimac${NC}"
echo ""
echo -e "${BLUE}Note:${NC} Administrator privileges recommended for hardware monitoring"
echo ""

# Offer to launch
read -p "Launch GerdsenAI OptiMac now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${BLUE}Launching GerdsenAI OptiMac v2.0...${NC}"
    open "$INSTALL_DIR/GerdsenAI OptiMac v2.command"
fi

echo ""
echo -e "${GREEN}Setup complete! Enjoy optimizing your Mac!${NC}"
