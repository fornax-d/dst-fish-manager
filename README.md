# DST Fish Manager 🐟

## Structure

```
dst-fish-manager/
├── ui/                        # UI layer
│   ├── app.py                # Main TUI application
│   ├── components/           # UI components
│   │   ├── windows.py        # Window management
│   │   ├── popups.py        # Popup components
│   │   └── settings.py      # Settings management
│   ├── input/                # Input handling
│   │   └── handler.py        # Input handler
│   └── rendering/            # Rendering system
│       ├── renderer.py        # Main renderer
│       └── themes.py         # Color themes
├── core/                     # Core functionality
│   ├── state/                # State management
│   │   └── app_state.py     # Application state
│   ├── events/               # Event system
│   │   └── bus.py           # Event bus
│   └── background/           # Background tasks
│       └── coordinator.py    # Task coordinator
├── features/                 # Feature modules
│   ├── mods/                # Mod management
│   │   └── mod_manager.py    # Mod manager
│   ├── chat/                # Chat management
│   │   └── chat_manager.py    # Chat manager
│   ├── status/              # Status monitoring
│   │   └── status_manager.py  # Status manager
│   ├── shards/              # Shard management
│   │   └── shard_manager.py   # Shard manager
│   └── cluster/             # Cluster management
│       └── cluster_manager.py # Cluster manager
├── services/                 # Service layer
│   ├── manager_service.py    # Main manager service
│   ├── game_service.py      # Game communication
│   └── systemd_service.py   # SystemD integration
├── utils/                    # Utilities
│   ├── config.py            # Configuration
│   └── helpers.py           # Helper functions
├── .config/                  # Configuration files
│   ├── systemd/user/         # SystemD service files
│   │   ├── dontstarve.target
│   │   └── dontstarve@.service
│   └── dontstarve/          # DST configuration
│       ├── config
│       └── shards.conf
├── .local/bin/               # Executable scripts
│   ├── dst-tui              # Main TUI wrapper
│   ├── dst-server           # Server management script
│   └── dst-updater          # Update script
├── install.fish             # Installation script (Fish shell)
├── DOCUMENTATION.md         # Complete technical documentation
└── main.py                  # Entry point
```

## FEATURES

1. **Separation of Concerns** - Clear separation between UI, state, and business logic
2. **Event-Driven Architecture** - Decoupled communication via event bus
3. **State Management** - Centralized, thread-safe state management
4. **Modular Services** - Service layer for external integrations
5. **Component-Based UI** - Reusable UI components
6. **Background Coordination** - Organized background task handling

## Running

### Prerequisites
- **Fish Shell**: Installation script requires Fish shell
- **PATH Configuration**: Ensure `~/.local/bin` is in your PATH

### Method 1: Using the wrapper script (Recommended)
```bash
dst-tui
```

### Method 2: Direct Python execution
```bash
cd dst-fish-manager
python main.py
```

### Method 3: Using Fish wrapper directly
```bash
fish ~/.local/bin/dst-tui
```

## Requirements

### System Requirements
- **Linux**: systemd-based distribution (Ubuntu, Debian, Fedora, Arch)
- **Fish Shell**: Required for installation scripts (recommended shell)
- **Python 3.8+**: Core runtime environment
- **systemd**: Service management system

### Installing Fish Shell

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install fish
```

#### Fedora/RHEL/CentOS
```bash
sudo dnf install fish
```

#### Arch Linux
```bash
sudo pacman -S fish
```

#### Set Fish as Default Shell (Optional)
```bash
chsh -s $(which fish)
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
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

3. Run automated installation (uses Fish shell):
```bash
# Make sure fish is installed, then run:
./install.fish
```

**OR** Manual installation (if you prefer not to use Fish):
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

# Add ~/.local/bin to PATH (for bash/zsh)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
# or for zsh:
# echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

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
- `CLUSTER_NAME`: Your cluster name (or "auto" for auto-detection)
- `BRANCH`: Game branch (main, beta, staging)
- `INSTALL_DIR`: DST server installation directory
- `DONTSTARVE_DIR`: Game saves directory

Edit `~/.config/dontstarve/shards.conf` to list your shards.
