#!/bin/bash

# Frigate + MemryX Launcher Script
# This script sets up and launches the Frigate management GUI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration flags
FRIGATE_UPDATE_FLAG=true  # Set to false to skip Frigate updates

# Auto-update function for the control panel
check_and_update_control_panel() {
    echo "🔍 Checking for Frigate Control Panel updates..."
    
    # Check if we're in a git repository
    if [ -d ".git" ]; then
        # Fetch latest changes quietly
        if git fetch origin main 2>/dev/null; then
            # Check if there are updates available
            LOCAL=$(git rev-parse HEAD 2>/dev/null)
            REMOTE=$(git rev-parse origin/main 2>/dev/null)
            
            if [ "$LOCAL" != "$REMOTE" ] && [ -n "$LOCAL" ] && [ -n "$REMOTE" ]; then
                echo "📥 Control panel updates available! Pulling latest changes..."
                
                # Stash any local changes to prevent conflicts
                git stash push -m "Auto-stash before update $(date)" 2>/dev/null
                
                # Pull latest changes
                if git pull origin main 2>/dev/null; then
                    echo "✅ Control panel updated successfully!"
                    
                    # Check if launch.sh was updated
                    if git diff --name-only HEAD~1 HEAD | grep -q "launch.sh"; then
                        echo "🔄 Launch script updated! Restarting with new version..."
                        chmod +x launch.sh  # Ensure it's still executable
                        exec "$0" "$@"  # Restart the script with new version
                    fi
                else
                    echo "⚠️  Failed to update control panel, continuing with current version..."
                fi
            else
                echo "✅ Control panel is up to date!"
            fi
        else
            echo "⚠️  Could not check for updates (no internet or git issues)"
        fi
    else
        echo "ℹ️  Not a git repository, skipping auto-update"
    fi
    echo ""
}

# Auto-update function for Frigate
update_frigate_if_enabled() {
    if [ "$FRIGATE_UPDATE_FLAG" = true ]; then
        echo "🔄 Frigate update flag is enabled - checking for Frigate updates..."
        
        # Check if frigate directory exists
        if [ -d "frigate" ]; then
            echo "📥 Updating existing Frigate installation..."
            cd frigate
            if [ -d ".git" ]; then
                git fetch origin dev 2>/dev/null
                LOCAL_FRIGATE=$(git rev-parse HEAD 2>/dev/null)
                REMOTE_FRIGATE=$(git rev-parse origin/dev 2>/dev/null)
                
                if [ "$LOCAL_FRIGATE" != "$REMOTE_FRIGATE" ] && [ -n "$LOCAL_FRIGATE" ] && [ -n "$REMOTE_FRIGATE" ]; then
                    echo "📥 Frigate updates available! Pulling latest changes..."
                    git pull origin dev 2>/dev/null && echo "✅ Frigate updated successfully!" || echo "⚠️  Frigate update failed"
                else
                    echo "✅ Frigate is up to date!"
                fi
            else
                echo "⚠️  Frigate directory exists but is not a git repository"
            fi
            cd "$SCRIPT_DIR"
        else
            echo "ℹ️  Frigate not installed yet - will be installed during setup process"
        fi
    else
        echo "⏭️  Frigate update flag is disabled - skipping Frigate updates"
    fi
    echo ""
}

# Run auto-update checks
check_and_update_control_panel
update_frigate_if_enabled

# Detect if running in GUI mode and setup logging
if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
    # GUI mode - create a log file
    LOG_FILE="$SCRIPT_DIR/launcher.log"
    echo "🖥️ Running in GUI mode - logging to: $LOG_FILE"
    
    # Redirect output to both console and log file
    exec > >(tee "$LOG_FILE") 2>&1
fi

echo "🚀 Starting Frigate + MemryX Control Center..."
echo "📍 Working directory: $SCRIPT_DIR"

# One-time setup function
setup_desktop_integration() {
    echo "🔧 Setting up desktop integration..."
    
    # Make scripts executable
    chmod +x launch.sh
    
    # Create .desktop file dynamically with correct paths
    echo "📝 Creating desktop entry file..."
    cat > frigate-launcher.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Frigate + MemryX Control Center
Comment=Manage Frigate installation and configuration with MemryX acceleration
Icon=${SCRIPT_DIR}/assets/frigate.png
Exec=${SCRIPT_DIR}/launch.sh
Terminal=false
StartupNotify=true
Categories=Development;System;
Keywords=Frigate;MemryX;Camera;Surveillance;AI;
EOF
    
    # Make the created .desktop file executable
    chmod +x frigate-launcher.desktop
    
    # Create desktop shortcut if desktop directory exists
    if [ -d "$HOME/Desktop" ]; then
        echo "🖥️ Creating desktop shortcuts..."
        cp frigate-launcher.desktop "$HOME/Desktop/" 2>/dev/null || true
        chmod +x "$HOME/Desktop/frigate-launcher.desktop" 2>/dev/null || true
    fi
    
    # Create system-wide desktop entry if applications directory exists
    if [ -d "$HOME/.local/share/applications" ]; then
        echo "📱 Creating application menu entries..."
        cp frigate-launcher.desktop "$HOME/.local/share/applications/" 2>/dev/null || true
    fi
    
    # Create a marker file to indicate setup is complete
    touch "$SCRIPT_DIR/.setup_complete"
    echo "✅ Desktop integration setup complete!"
}

# Check if this is the first run
if [ ! -f "$SCRIPT_DIR/.setup_complete" ]; then
    echo ""
    echo "🎯 First-time setup detected..."
    setup_desktop_integration
    echo ""
fi

# Check if Python is available and install if needed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    
    # Check if we're running in a GUI environment without terminal
    if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
        # GUI environment - use GUI tools for installation
        echo "🖥️ Detected GUI environment - using GUI installation method..."
        
        # Try to use GUI sudo tools
        if command -v pkexec &> /dev/null; then
            echo "🔧 Using pkexec for GUI installation..."
            if command -v apt &> /dev/null; then
                # Use pkexec for GUI sudo
                pkexec bash -c "apt update && apt install -y python3 python3-pip python3-venv python3-dev" || {
                    echo "❌ GUI installation failed or was cancelled."
                    echo "📝 Please install Python 3 manually using your package manager"
                    echo "   or run this script from a terminal: ./launch.sh"
                    exit 1
                }
            else
                echo "❌ Automatic GUI installation not supported on this system."
                echo "📝 Please install Python 3 manually or run from terminal"
                exit 1
            fi
        elif command -v gksudo &> /dev/null; then
            echo "� Using gksudo for GUI installation..."
            if command -v apt &> /dev/null; then
                gksudo "apt update && apt install -y python3 python3-pip python3-venv python3-dev" || {
                    echo "❌ GUI installation failed or was cancelled."
                    echo "� Please install Python 3 manually or run from terminal"
                    exit 1
                }
            fi
        else
            # No GUI sudo available - show instructions
            echo "❌ No GUI installation method available."
            echo "📝 Please install Python 3 manually:"
            echo "   • Open terminal and run: sudo apt install python3 python3-pip python3-venv python3-dev"
            echo "   • Or run this launcher from terminal: ./launch.sh"
            echo "   • Or use your system's software center to install Python 3"
            
            # Try to open terminal with instructions
            if command -v gnome-terminal &> /dev/null; then
                gnome-terminal -- bash -c "echo 'Please run: sudo apt install python3 python3-pip python3-venv python3-dev'; echo 'Then close this terminal and try launching again.'; read -p 'Press Enter to close...'"
            elif command -v konsole &> /dev/null; then
                konsole -e bash -c "echo 'Please run: sudo apt install python3 python3-pip python3-venv python3-dev'; echo 'Then close this terminal and try launching again.'; read -p 'Press Enter to close...'"
            fi
            exit 1
        fi
    else
        # Terminal environment - use traditional sudo
        echo "🔧 Attempting to install Python 3 automatically..."
        
        # Check if we're on a Debian/Ubuntu system
        if command -v apt &> /dev/null; then
            echo "📦 Installing Python 3 using apt package manager..."
            
            # Try to install without sudo first (in case user has passwordless sudo)
            if sudo -n true 2>/dev/null; then
                echo "🔓 Using existing sudo privileges..."
                sudo apt update && sudo apt install -y python3 python3-pip python3-venv python3-dev
            else
                echo "🔐 Please enter your password to install Python 3:"
                sudo apt update && sudo apt install -y python3 python3-pip python3-venv python3-dev
            fi
        else
            echo "❌ Automatic installation not supported on this system."
            echo "📝 Please install Python 3 manually:"
            echo "   • On Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv python3-dev"
            echo "   • On CentOS/RHEL: sudo yum install python3 python3-pip"
            echo "   • On Fedora: sudo dnf install python3 python3-pip"
            echo "   • On Arch: sudo pacman -S python python-pip"
            exit 1
        fi
    fi
    
    # Verify installation
    if command -v python3 &> /dev/null; then
        echo "✅ Python 3 installed successfully!"
        python3 --version
    else
        echo "❌ Failed to install Python 3. Please install manually:"
        echo "   sudo apt update && sudo apt install python3 python3-pip python3-venv python3-dev"
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist or is corrupted
VENV_DIR="$SCRIPT_DIR/.venv"
PIP_PATH="$VENV_DIR/bin/pip"

# Check if virtual environment exists and is functional
if [ ! -d "$VENV_DIR" ] || [ ! -f "$PIP_PATH" ] || ! "$PIP_PATH" --version &>/dev/null; then
    if [ -d "$VENV_DIR" ]; then
        echo "🗑️ Removing corrupted virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    echo "🐍 Creating Python virtual environment..."
    if ! python3 -m venv "$VENV_DIR"; then
        echo "❌ Failed to create virtual environment."
        echo "🔧 Attempting to install python3-venv package..."
        
        # Check if we're in GUI or terminal environment
        if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
            # GUI environment
            if command -v pkexec &> /dev/null && command -v apt &> /dev/null; then
                echo "� Using GUI installation for python3-venv..."
                pkexec bash -c "apt update && apt install -y python3-venv" || {
                    echo "❌ GUI installation failed. Please install python3-venv manually."
                    exit 1
                }
            elif command -v gksudo &> /dev/null && command -v apt &> /dev/null; then
                gksudo "apt update && apt install -y python3-venv" || {
                    echo "❌ GUI installation failed. Please install python3-venv manually."
                    exit 1
                }
            else
                echo "❌ Could not install python3-venv in GUI mode."
                echo "� Please install manually: sudo apt install python3-venv"
                exit 1
            fi
        else
            # Terminal environment
            if command -v apt &> /dev/null; then
                if sudo -n true 2>/dev/null; then
                    echo "🔓 Using existing sudo privileges..."
                    sudo apt update && sudo apt install -y python3-venv
                else
                    echo "🔐 Please enter your password to install python3-venv:"
                    sudo apt update && sudo apt install -y python3-venv
                fi
            else
                echo "❌ Could not install python3-venv automatically."
                echo "📝 Please install python3-venv manually:"
                echo "   • On Ubuntu/Debian: sudo apt install python3-venv"
                echo "   • On CentOS/RHEL: sudo yum install python3-venv"
                echo "   • On Fedora: sudo dnf install python3-venv"
                exit 1
            fi
        fi
        
        # Try creating venv again
        echo "🐍 Retrying virtual environment creation..."
        if ! python3 -m venv "$VENV_DIR"; then
            echo "❌ Still failed to create virtual environment. Please check your Python installation."
            exit 1
        fi
    fi
    
    # Verify the virtual environment was created successfully
    if [ ! -f "$PIP_PATH" ]; then
        echo "❌ Virtual environment creation failed completely."
        exit 1
    fi
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Verify activation worked
if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Install/upgrade required packages
echo "📦 Installing/updating required Python packages..."
if ! pip install --upgrade pip; then
    echo "⚠️ Failed to upgrade pip, continuing with existing version..."
fi

echo "📦 Installing PySide6 and PyYAML..."
if ! pip install PySide6 PyYAML; then
    echo "❌ Failed to install required packages."
    echo "🔧 This might be due to missing system dependencies."
    echo "📝 You may need to install additional packages:"
    echo "   sudo apt install python3-dev build-essential"
    echo ""
    echo "🔄 Attempting to install system dependencies..."
    
    # Check if we're in GUI or terminal environment
    if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
        # GUI environment
        if command -v pkexec &> /dev/null && command -v apt &> /dev/null; then
            echo "🔧 Using GUI installation for build dependencies..."
            pkexec bash -c "apt update && apt install -y python3-dev build-essential" || {
                echo "❌ GUI installation failed. Please install build dependencies manually."
                exit 1
            }
        elif command -v gksudo &> /dev/null && command -v apt &> /dev/null; then
            gksudo "apt update && apt install -y python3-dev build-essential" || {
                echo "❌ GUI installation failed. Please install build dependencies manually."
                exit 1
            }
        else
            echo "❌ Could not install build dependencies in GUI mode."
            echo "📝 Please install manually: sudo apt install python3-dev build-essential"
            echo "   Then run this launcher again."
            exit 1
        fi
    else
        # Terminal environment
        if command -v apt &> /dev/null; then
            if sudo -n true 2>/dev/null; then
                sudo apt update && sudo apt install -y python3-dev build-essential
            else
                echo "🔐 Please enter your password to install system dependencies:"
                sudo apt update && sudo apt install -y python3-dev build-essential
            fi
        else
            echo "❌ Could not install system dependencies automatically."
            exit 1
        fi
    fi
    
    echo "🔄 Retrying package installation..."
    if ! pip install PySide6 PyYAML; then
        echo "❌ Still failed to install packages. Please check the error messages above."
        exit 1
    fi
fi

# Check network configuration for camera discovery
echo "🔍 Checking network configuration for camera discovery..."

# Check if multicast is supported
if command -v ip >/dev/null 2>&1; then
    NETWORK_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
    if [ -n "$NETWORK_INTERFACE" ]; then
        echo "📡 Primary network interface: $NETWORK_INTERFACE"
        
        # Check if interface supports multicast
        if ip link show "$NETWORK_INTERFACE" | grep -q "MULTICAST"; then
            echo "✅ Multicast supported on $NETWORK_INTERFACE"
        else
            echo "⚠️  Multicast may not be supported on $NETWORK_INTERFACE"
            echo "   This could affect camera discovery functionality"
        fi
        
        # Check local IP
        LOCAL_IP=$(ip addr show "$NETWORK_INTERFACE" | grep "inet " | awk '{print $2}' | cut -d/ -f1 | head -n1)
        if [ -n "$LOCAL_IP" ]; then
            echo "🌐 Local IP address: $LOCAL_IP"
            
            # Provide network troubleshooting info
            echo ""
            echo "📋 Camera Discovery Troubleshooting:"
            echo "   - Ensure cameras are on the same network as this computer ($LOCAL_IP/24)"
            echo "   - Check if firewall allows multicast traffic (UDP port 3702)"
            echo "   - Verify cameras support ONVIF WS-Discovery"
            echo "   - Some routers block multicast traffic between subnets"
        fi
    fi
else
    echo "⚠️  Cannot detect network configuration (ip command not available)"
fi

echo ""
echo "🎮 Launching Frigate Control Center..."

python frigate_launcher.py

echo ""
echo "👋 Frigate Control Center closed."

# Show helpful info on first run
if [ -f "$SCRIPT_DIR/.setup_complete" ] && [ ! -f "$SCRIPT_DIR/.info_shown" ]; then
    echo ""
    echo "💡 Next time you can also:"
    echo "   • Double-click the desktop shortcut"
    echo "   • Find 'Frigate + MemryX Control Center' in your applications menu"
    echo "   • Run this script again: ./launch.sh"
    touch "$SCRIPT_DIR/.info_shown"
fi
