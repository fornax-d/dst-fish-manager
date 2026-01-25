<img width="1593" height="916" alt="Zrzut ekranu_20260125_204928" src="https://github.com/user-attachments/assets/00dd94e3-01a6-4dea-96de-714ac64ea7fb" />

# DST Fish Manager 🐟

A Terminal UI manager for Don't Starve Together dedicated servers.

## Features
- **TUI Interface**: Manage your server with a clean, curses-based UI.
- **Process Isolation**: The manager runs independently of the server processes.
- **Discord Integration**: Optional `fall.bot` plugin for 2-way chat & server control.

## Installation

1. **Clone & Deps**:
```bash
git clone https://github.com/fornax-d/dst-fish-manager.git
cd dst-fish-manager
sudo apt install python3-curses fish  # Or equivalent for your distro
pip install -r requirements.txt       # For Discord bot support
```

2. **Install Scripts**:
```bash
fish ./install.fish
```
This installs `dst-tui` and configs to `~/.config/dontstarve/`.

## Running
```bash
dst-tui
```

## Configuration
Edit `~/.config/dontstarve/config`:
- `CLUSTER_NAME`: "MyDediServer"
- `INSTALL_DIR`: Path to server bin
