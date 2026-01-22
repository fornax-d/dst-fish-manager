# DST Fish Manager 🐟

## FEATURES

1. **Separation of Concerns** - Separation between UI, state, and business logic
2. **Event-Driven Architecture** - Decoupled communication via event bus
3. **State Management** - Centralized state management
4. **Modular Services** - Service layer for external integrations
5. **Background Coordination** - Organized background task handling

## Running

### Method 1: Using the wrapper script (Recommended)
```bash
dst-tui
```

### Method 2: Direct Python execution
```bash
cd dst-fish-manager
python main.py
```

## Requirements

### System Requirements
- **Linux**: systemd-based distribution (Ubuntu, Debian, Fedora, Arch)
- **Fish Shell** 🐠
- **Python 3.8+**: Core runtime environment


## Installation

1. Clone the repository:
```bash
git clone https://github.com/fornax-d/dst-fish-manager.git
cd dst-fish-manager
```

2. Install required dependencies:
```bash
# Ensure Python 3.8+ is installed
python3 --version

# Install system dependencies if needed
sudo apt install python3-curses  # For Debian/Ubuntu
# or on Fedora:
# sudo dnf install python3-curses
```

3. Automated installation:
```bash
./install.fish
```

**OR** Manual installation:
```bash
# Create directories
mkdir -p ~/.config/systemd/user
mkdir -p ~/.config/dontstarve
mkdir -p ~/.local/bin

# Copy configuration files
cp -r .config/systemd/user/* ~/.config/systemd/user/
cp -r .config/dontstarve/* ~/.config/dontstarve/
cp .local/bin/dst-* ~/.local/bin/

# Set permissions
chmod +x ~/.local/bin/dst-*

# Reload systemd
systemctl --user daemon-reload
```

4. Verify installation:
```bash
# Check if scripts are accessible
which dst-tui  # Should show ~/.local/bin/dst-tui

# Test the application
dst-tui --help
```

## Configuration

Edit `~/.config/dontstarve/config` to set:
- `CLUSTER_NAME`: Your cluster name (leave "auto" for auto-detection)
- `BRANCH`: Game branch (main, beta)
- `INSTALL_DIR`: DST server installation directory
- `DONTSTARVE_DIR`: Game saves directory

Edit `~/.config/dontstarve/shards.conf` to list your shards.
